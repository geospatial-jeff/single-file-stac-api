"""single_file_stac_api.backend"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

from rtree import index
from stac_api import config
from stac_api.clients.base import BaseCoreClient, BaseTransactionsClient, NumType
from stac_api.models import schemas
from stac_api.models.links import CollectionLinks, ItemLinks
from stac_pydantic import Collection, Item, ItemCollection
from stac_pydantic.api import ConformanceClasses, LandingPage
from stac_pydantic.extensions.single_file_stac import SingleFileStac
from stac_pydantic.shared import Link, MimeTypes, Relations


@dataclass
class Database:
    """cheapo spatial database.

    https://rtree.readthedocs.io/en/latest/tutorial.html#using-rtree-as-a-cheapo-spatial-database
    """

    collections: List[Collection] = field(default_factory=list)
    items: List[Item] = field(default_factory=list)

    def __post_init__(self):
        """post init handler"""
        self.host = f"http://{config.settings.host}:{config.settings.port}"
        self.index = index.Index()

    def intersects(self, bbox):
        """find all items which intersect the bbox."""
        return [n.object for n in self.index.intersection(bbox, objects=True)]

    def insert_item(self, item: Item):
        """Insert an item into the database."""
        item_links = ItemLinks(
            collection_id=item.collection, item_id=item.id, base_url=self.host
        ).create_links()
        item.links += item_links
        self.index.insert(len(self.items) + 1, item.bbox, obj=item)
        self.items.append(item)

    def insert_collection(self, collection: Collection):
        """Insert collection into the database."""
        collection_links = CollectionLinks(
            collection_id=collection.id, base_url=self.host
        ).create_links()
        collection.links += collection_links
        self.collections.append(collection)


@dataclass
class SingleFileClient(BaseTransactionsClient, BaseCoreClient):
    """application logic"""

    db: Database

    @classmethod
    def from_file(cls, filename: str):
        """create from file."""
        data = SingleFileStac.parse_file(filename)
        db = Database()

        for collection in data.collections:
            db.insert_collection(collection)

        for item in data.features:
            db.insert_item(item)

        return cls(db=db)

    def landing_page(self, **kwargs) -> LandingPage:
        """GET /"""
        return LandingPage(
            title="Single File STAC",
            description="Single File STAC",
            links=[
                Link(
                    rel=Relations.self,
                    type=MimeTypes.json,
                    href=str(kwargs["request"].base_url),
                ),
                Link(
                    rel=Relations.docs,
                    type=MimeTypes.html,
                    title="OpenAPI docs",
                    href=urljoin(str(kwargs["request"].base_url), "/docs"),
                ),
                Link(
                    rel=Relations.conformance,
                    type=MimeTypes.json,
                    title="STAC/WFS3 conformance classes implemented by this server",
                    href=urljoin(str(kwargs["request"].base_url), "/conformance"),
                ),
                Link(
                    rel=Relations.search,
                    type=MimeTypes.geojson,
                    title="STAC search",
                    href=urljoin(str(kwargs["request"].base_url), "/search"),
                ),
            ],
        )

    def conformance(self, **kwargs) -> ConformanceClasses:
        """GET /conformance"""
        return ConformanceClasses(
            conformsTo=[
                "https://stacspec.org/STAC-api.html",
                "http://docs.opengeospatial.org/is/17-069r3/17-069r3.html#ats_geojson",
            ]
        )

    def all_collections(self, **kwargs) -> List[schemas.Collection]:
        """GET /collections"""
        return self.db.collections

    def get_collection(self, id: str, **kwargs) -> schemas.Collection:
        """GET /collections/{collectionId}"""
        for coll in self.db.collections:
            if coll.id == id:
                return coll

    def item_collection(
        self, id: str, limit: int = 10, token: str = None, **kwargs
    ) -> ItemCollection:
        """GET /collections/{collectionId}/items"""
        matches = []
        for item in self.db.items:
            if item.collection == id:
                matches.append(item)
        return ItemCollection(features=matches, links=[])

    def get_item(self, id: str, **kwargs) -> schemas.Item:
        """GET /collections/{collectionId}/items/{itemId}"""
        for item in self.db.items:
            if item.id == id:
                return item

    def post_search(
        self, search_request: schemas.STACSearch, **kwargs
    ) -> Dict[str, Any]:
        """POST /search"""
        if search_request.ids:
            items = [item for item in self.db.items if item.id in search_request.ids]
        else:
            poly = search_request.polygon()
            if poly:
                items = self.db.intersects(poly.bounds)
            else:
                items = self.db.items

        if search_request.collections:
            items = [
                item for item in items if item.collection in search_request.collections
            ]

        return {
            "type": "FeatureCollection",
            "features": [i.dict() for i in items],
            "links": [],
        }

    def get_search(
        self,
        collections: Optional[List[str]] = None,
        ids: Optional[List[str]] = None,
        bbox: Optional[List[NumType]] = None,
        datetime: Optional[Union[str, datetime]] = None,
        limit: Optional[int] = 10,
        query: Optional[str] = None,
        token: Optional[str] = None,
        fields: Optional[List[str]] = None,
        sortby: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """GET /search"""
        # Parse request parameters
        base_args = {
            "collections": collections,
            "ids": ids,
            "bbox": bbox,
            "limit": limit,
            "token": token,
        }
        if datetime:
            base_args["datetime"] = datetime

        # Do the request
        search_request = schemas.STACSearch(**base_args)
        return self.post_search(search_request, request=kwargs["request"])

    def create_collection(
        self, model: schemas.Collection, **kwargs
    ) -> schemas.Collection:
        """POST /collections"""
        self.db.insert_collection(model)
        return model

    def create_item(self, model: schemas.Item, **kwargs) -> schemas.Item:
        """POST /collections/{collectionId}/items"""
        self.db.insert_item(model)
        return model

    def delete_collection(self, id: str, **kwargs) -> schemas.Collection:
        """DELETE /collections/{collectionId}"""
        for idx, collection in enumerate(self.db.collections):
            if collection.id == id:
                break
        self.db.collections.pop(idx)

    def delete_item(self, id: str, **kwargs) -> schemas.Item:
        """DELETE /collections/{collectionId}/items/{itemId}"""
        # TODO: I have no idea how to remove something from an `rtree.index.Index`
        raise NotImplementedError

    def update_collection(
        self, model: schemas.Collection, **kwargs
    ) -> schemas.Collection:
        """PUT /collections/{collectionId}"""
        self.delete_collection(model.id)
        self.db.insert_collection(model)

    def update_item(self, model: schemas.Item, **kwargs) -> schemas.Item:
        # TODO: Same
        """PUT /collections/{collectionId}/items/{itemId}"""
        raise NotImplementedError
