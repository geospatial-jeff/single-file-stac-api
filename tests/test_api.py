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
