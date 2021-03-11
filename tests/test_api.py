from shapely.geometry import Polygon, shape
from stac_pydantic import Collection, Item, ItemCollection
from stac_pydantic.api import LandingPage

COLLECTION_ID = "joplin"
ITEM_ID = "f2cca2a3-288b-4518-8a3e-a4492bb60b08"


def test_landing_page(app_client):
    resp = app_client.get("/")
    assert resp.status_code == 200
    LandingPage.parse_obj(resp.json())


def test_get_collections(app_client):
    resp = app_client.get("/collections")
    assert resp.status_code == 200
    for collection in resp.json():
        Collection.parse_obj(collection)


def test_get_collection(app_client):
    resp = app_client.get(f"/collections/{COLLECTION_ID}")
    assert resp.status_code == 200
    collection = Collection.parse_obj(resp.json())
    assert collection.id == COLLECTION_ID


def test_get_item_collection(app_client):
    resp = app_client.get(f"/collections/{COLLECTION_ID}/items")
    assert resp.status_code == 200
    item_collection = ItemCollection.parse_obj(resp.json())
    for item in item_collection.features:
        assert item.collection == COLLECTION_ID


def test_get_item(app_client):
    resp = app_client.get(f"/collections/{COLLECTION_ID}/items/{ITEM_ID}")
    assert resp.status_code == 200
    item = Item.parse_obj(resp.json())
    assert item.collection == COLLECTION_ID
    assert item.id == ITEM_ID


def test_get_search_ids(app_client):
    params = {"ids": [ITEM_ID]}
    resp = app_client.get("/search", params=params)
    assert resp.status_code == 200
    item_collection = ItemCollection.parse_obj(resp.json())
    assert len(item_collection.features) == len(params["ids"])
    assert item_collection.features[0].id == ITEM_ID


def test_get_search_collection(app_client):
    params = {"collections": [COLLECTION_ID]}
    resp = app_client.get("/search", params=params)
    assert resp.status_code == 200
    item_collection = ItemCollection.parse_obj(resp.json())
    for item in item_collection.features:
        assert item.collection == COLLECTION_ID

    params = {"collections": ["another-collection"]}
    resp = app_client.get("/search", params=params)
    assert resp.status_code == 200
    assert len(resp.json()["features"]) == 0


def test_get_search_bbox(app_client):
    resp = app_client.get(f"/collections/{COLLECTION_ID}/items/{ITEM_ID}")
    assert resp.status_code == 200
    item = Item.parse_obj(resp.json())

    # Find other items that intersect the bounds of the item
    params = {
        "bbox": ",".join([str(v) for v in item.bbox]),
        "collections": [item.collection],
    }
    resp = app_client.get("/search", params=params)
    assert resp.status_code == 200
    item_collection = ItemCollection.parse_obj(resp.json())

    request_geom = Polygon.from_bounds(*item.bbox)
    for item in item_collection.features:
        geom = shape(item.geometry)
        assert geom.intersects(request_geom)


def test_post_search_intersects(app_client):
    resp = app_client.get(f"/collections/{COLLECTION_ID}/items/{ITEM_ID}")
    assert resp.status_code == 200
    item = Item.parse_obj(resp.json())

    # Find other items that intersect the bounds of the item
    body = {"intersects": item.geometry.dict(), "collections": [item.collection]}
    resp = app_client.post("/search", json=body)
    assert resp.status_code == 200

    item_collection = ItemCollection.parse_obj(resp.json())

    request_geom = Polygon.from_bounds(*item.bbox)
    for item in item_collection.features:
        geom = shape(item.geometry)
        assert geom.intersects(request_geom)


def test_app_query_extension(app_client):
    body = {"query": {"proj:epsg": {"gt": 10000}}}
    resp = app_client.post("/search", json=body)
    assert resp.status_code == 200
    resp_json = resp.json()
    assert len(resp_json["features"]) == 0


def test_app_pagging(app_client):
    body = {"limit": 1, "query": {"proj:epsg": {"lt": 10000}, "gsd": {"gt": 0.1}}}
    resp = app_client.post("/search", json=body)
    assert resp.status_code == 200
    resp_json = resp.json()
    assert resp_json["features"][0]["properties"]["gsd"]
    assert resp_json["features"][0]["properties"]["proj:epsg"]
    assert len(resp_json["features"]) == 1

    next_link = list(filter(lambda x: x["rel"] == "next", resp_json["links"]))
    assert next_link
    previous_link = list(filter(lambda x: x["rel"] == "previous", resp_json["links"]))
    assert not previous_link

    body["token"] = next_link[0]["body"]["token"]
    resp = app_client.post("/search", json=body)
    assert resp.status_code == 200
    resp_json_p2 = resp.json()
    assert not resp_json["features"][0]["id"] == resp_json_p2["features"][0]["id"]

    next_link = list(filter(lambda x: x["rel"] == "next", resp_json_p2["links"]))
    assert next_link
    previous_link = list(
        filter(lambda x: x["rel"] == "previous", resp_json_p2["links"])
    )
    assert previous_link

    body["token"] = previous_link[0]["body"]["token"]
    resp = app_client.post("/search", json=body)
    assert resp.status_code == 200
    resp_json_p1 = resp.json()
    assert resp_json["features"][0]["id"] == resp_json_p1["features"][0]["id"]

    body["token"] = "NotAGoodToken"
    resp = app_client.post("/search", json=body)
    assert resp.status_code == 404


def test_app_search_datetime(app_client):
    body = {"limit": 1, "datetime": "2000-02-01T00:00:00Z/2000-02-03T00:00:00Z"}
    resp = app_client.post("/search", json=body)
    assert resp.status_code == 200
    resp_json = resp.json()
    assert resp_json["context"]["matched"] == 30
    assert len(resp_json["features"]) == 1

    body = {"limit": 1, "datetime": "../2000-02-03T00:00:00Z"}
    resp = app_client.post("/search", json=body)
    assert resp.status_code == 200
    resp_json = resp.json()
    assert resp_json["context"]["matched"] == 30
    assert len(resp_json["features"]) == 1

    body = {"limit": 1, "datetime": "2000-02-01T00:00:00Z/.."}
    resp = app_client.post("/search", json=body)
    assert resp.status_code == 200
    resp_json = resp.json()
    assert resp_json["context"]["matched"] == 30
    assert len(resp_json["features"]) == 1

    resp = app_client.get(
        "/search", params={"datetime": "2000-02-01T00:00:00Z/2000-02-03T00:00:00Z"}
    )
    assert resp.status_code == 200
    resp_json = resp.json()
    assert resp_json["context"]["matched"] == 30


def test_app_search_fields(app_client):
    resp = app_client.get("/search", params={"limit": 1})
    assert resp.status_code == 200
    resp_json = resp.json()
    assert resp_json["context"]["matched"] == 30
    assert len(resp_json["features"]) == 1
    assert list(resp_json["features"][0]["properties"]) == ["datetime"]

    resp = app_client.get("/search", params={"limit": 1, "fields": ["+properties.gsd"]})
    assert resp.status_code == 200
    resp_json = resp.json()
    assert resp_json["context"]["matched"] == 30
    assert len(resp_json["features"]) == 1
    assert "gsd" in list(resp_json["features"][0]["properties"])

    resp = app_client.get("/search", params={"limit": 1, "fields": ["properties.gsd"]})
    assert resp.status_code == 200
    resp_json = resp.json()
    assert resp_json["context"]["matched"] == 30
    assert len(resp_json["features"]) == 1
    assert "gsd" in list(resp_json["features"][0]["properties"])

    resp = app_client.get("/search", params={"limit": 1, "fields": ["-links"]})
    assert resp.status_code == 200
    resp_json = resp.json()
    assert resp_json["context"]["matched"] == 30
    assert len(resp_json["features"]) == 1
    assert "links" not in list(resp_json["features"][0])
