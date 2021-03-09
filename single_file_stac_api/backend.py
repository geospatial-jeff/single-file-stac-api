"""single_file_stac_api.backend"""
import json
import os
from base64 import urlsafe_b64encode
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode, urljoin

import attr
from pydantic import BaseModel
from pygeos import Geometry, STRtree, polygons
from pygeos.io import from_shapely
from stac_api.api.extensions import ContextExtension, FieldsExtension
from stac_api.clients.base import BaseCoreClient, BaseTransactionsClient, NumType
from stac_api.errors import NotFoundError
from stac_api.models import schemas
from stac_api.models.links import CollectionLinks, ItemLinks
from stac_pydantic import Collection, Item, ItemCollection
from stac_pydantic.api import ConformanceClasses, LandingPage
from stac_pydantic.api.extensions.paging import PaginationLink
from stac_pydantic.extensions.single_file_stac import SingleFileStac
from stac_pydantic.shared import Link, MimeTypes, Relations

from single_file_stac_api.config import settings


@attr.s
class Database:
    """cheapo spatial database.

    https://rtree.readthedocs.io/en/latest/tutorial.html#using-rtree-as-a-cheapo-spatial-database
    """

    host: str = attr.ib(default=f"http://{settings.host}:{settings.port}")
    collections: List[Collection] = attr.ib(factory=list)
    items: List[Item] = attr.ib(factory=list)

    index: STRtree = STRtree([])

    def intersects(self, geom: Geometry):
        """find all items which intersect the bbox."""
        idx = self.index.query(geom, predicate="intersects").tolist()
        return [self.items[n] for n in idx]

    def bulk_insert_items(self, items: List[Item]):
        """Insert items into the database."""
        for item in items:
            item_links = ItemLinks(
                collection_id=item.collection, item_id=item.id, base_url=self.host
            ).create_links()
            item.links += item_links
            self.items.append(item)

        self.index = STRtree([polygons(item.geometry.coordinates[0]) for item in items])

    def bulk_insert_collections(self, collections: List[Collection]):
        """Insert collections into the database."""
        for collection in collections:
            collection_links = CollectionLinks(
                collection_id=collection.id, base_url=self.host
            ).create_links()
            collection.links += collection_links
            self.collections.append(collection)

    def insert_item(self, item: Item):
        """Insert items into the database."""
        # re-create STRtree from items
        raise NotImplementedError

    def insert_collection(self, collection: Collection):
        """Insert collection into the database."""
        collection_links = CollectionLinks(
            collection_id=collection.id, base_url=self.host
        ).create_links()
        collection.links += collection_links
        self.collections.append(collection)


class PaginationToken(BaseModel):
    """Pagination model."""

    id: str
    keyset: str


@attr.s
class PaginationTokenClient:
    """Pagination token."""

    token_table: List[PaginationToken] = attr.ib(factory=list)

    def insert_token(self, keyset: str, tries: int = 0) -> str:  # type:ignore
        """Insert a keyset into the database."""
        # uid has collision chance of 1e-7 percent
        uid = urlsafe_b64encode(os.urandom(6)).decode()
        self.token_table.append(PaginationToken(id=uid, keyset=keyset))
        return uid

    def get_token(self, token_id: str) -> int:
        """Retrieve a keyset from the database."""
        rows = list(filter(lambda x: x.id == token_id, self.token_table))
        if not rows:
            raise NotFoundError(f"{token_id} not found")
        return int(rows[0].keyset)


@attr.s
class Paging:
    """Simple list Paging."""

    items: List = attr.ib()
    limit: int = attr.ib(default=10)

    def __attrs_post_init__(self):
        """Post Init."""
        num_pages = len(list(range(0, len(self.items), self.limit)))
        self.pages = [
            Page(
                items=self.items[i : i + self.limit],
                num=idx,
                has_next=(0 <= idx < num_pages - 1),
                has_previous=(0 < idx),
            )
            for idx, i in enumerate(range(0, len(self.items), self.limit))
        ]

    def get_page(self, page_number=None):
        """return page."""
        if not page_number:
            page_number = 0
        return list(filter(lambda x: x.num == page_number, self.pages))[0]


@attr.s
class Page:
    """Simple Page model."""

    items: List = attr.ib()
    num: int = attr.ib(default=0)
    has_next: bool = attr.ib(default=False)
    has_previous: bool = attr.ib(default=False)


@attr.s
class SingleFileClient(BaseTransactionsClient, BaseCoreClient, PaginationTokenClient):
    """application logic"""

    db: Database = attr.ib(factory=Database)

    @classmethod
    def from_file(cls, filename: str):
        """create from file."""
        data = SingleFileStac.parse_file(filename)
        db = Database()
        db.bulk_insert_collections(data.collections)
        db.bulk_insert_items(data.features)
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
        count = None
        token = self.get_token(search_request.token) if search_request.token else False

        # TODO: Sorting
        # # Default sort is date
        # query = query.order_by(
        #     self.item_table.datetime.desc(), self.item_table.id
        # )

        # Ignore other parameters if ID is present
        if search_request.ids:
            items = list(filter(lambda x: x.id in search_request.ids, self.db.items))
            pages = Paging(items, limit=search_request.limit)
            page = pages.get_page(token)
            if self.extension_is_enabled(ContextExtension):
                count = len(search_request.ids)

        else:
            # Spatial query
            poly = from_shapely(search_request.polygon())
            if poly:
                items = self.db.intersects(poly)
            else:
                items = self.db.items

            if search_request.collections:
                items = [
                    item
                    for item in items
                    if item.collection in search_request.collections
                ]

            # Temporal query
            if search_request.datetime:
                # Two tailed query (between)
                if ".." not in search_request.datetime:
                    start, end = search_request.datetime
                    items = list(filter(lambda x: start <= x.datetime < end, items))

                # All items after the start date
                if search_request.datetime[0] != "..":
                    start, _ = search_request.datetime
                    items = list(filter(lambda x: start <= x.datetime, items))

                # All items before the end date
                if search_request.datetime[1] != "..":
                    _, end = search_request.datetime
                    items = list(filter(lambda x: x.datetime <= end, items))

            # TODO: QUERY
            # # Query fields
            # if search_request.query:
            #     for (field_name, expr) in search_request.query.items():
            #         field = self.item_table.get_field(field_name)
            #         for (op, value) in expr.items():
            #             query = query.filter(op.operator(field, value))

            pages = Paging(items, limit=search_request.limit)
            page = pages.get_page(token)
            if self.extension_is_enabled(ContextExtension):
                count = len(items)

        links = []
        if page.has_next:
            next_page = self.insert_token(keyset=page.num + 1)
            links.append(
                PaginationLink(
                    rel=Relations.next,
                    type="application/geo+json",
                    href=f"{kwargs['request'].base_url}search",
                    method="POST",
                    body={"token": next_page},
                    merge=True,
                )
            )

        if page.has_previous:
            previous_page = self.insert_token(keyset=page.num - 1)
            links.append(
                PaginationLink(
                    rel=Relations.previous,
                    type="application/geo+json",
                    href=f"{kwargs['request'].base_url}search",
                    method="POST",
                    body={"token": previous_page},
                    merge=True,
                )
            )

        response_features = []
        filter_kwargs = {}
        if self.extension_is_enabled(FieldsExtension):
            filter_kwargs = search_request.field.filter_fields

        xvals = []
        yvals = []
        for item in page.items:
            # TODO
            # item.base_url = str(kwargs["request"].base_url)
            xvals += [item.bbox[0], item.bbox[2]]
            yvals += [item.bbox[1], item.bbox[3]]
            response_features.append(item.to_dict(**filter_kwargs))

        try:
            bbox = (min(xvals), min(yvals), max(xvals), max(yvals))
        except ValueError:
            bbox = None

        context_obj = None
        if self.extension_is_enabled(ContextExtension):
            context_obj = {
                "returned": len(page.items),
                "limit": search_request.limit,
                "matched": count,
            }

        return {
            "type": "FeatureCollection",
            "context": context_obj,
            "features": response_features,
            "links": links,
            "bbox": bbox,
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
            "query": json.loads(query) if query else query,
        }

        if datetime:
            base_args["datetime"] = datetime

        if sortby:
            # https://github.com/radiantearth/stac-spec/tree/master/api-spec/extensions/sort#http-get-or-post-form
            sort_param = []
            for sort in sortby:
                sort_param.append(
                    {
                        "field": sort[1:],
                        "direction": "asc" if sort[0] == "+" else "desc",
                    }
                )
            base_args["sortby"] = sort_param

        if fields:
            includes = set()
            excludes = set()
            for field in fields:
                if field[0] == "-":
                    excludes.add(field[1:])
                elif field[0] == "+":
                    includes.add(field[1:])
                else:
                    includes.add(field)
            base_args["fields"] = {"include": includes, "exclude": excludes}

        # Do the request
        search_request = schemas.STACSearch(**base_args)
        resp = self.post_search(search_request, request=kwargs["request"])

        # Pagination
        page_links = []
        for link in resp["links"]:
            if link.rel == Relations.next or link.rel == Relations.previous:
                query_params = dict(kwargs["request"].query_params)
                if link.body and link.merge:
                    query_params.update(link.body)
                link.method = "GET"
                link.href = f"{link.href}?{urlencode(query_params)}"
                link.body = None
                link.merge = False
                page_links.append(link)
            else:
                page_links.append(link)
        resp["links"] = page_links

        return resp

    def create_collection(
        self, model: schemas.Collection, **kwargs
    ) -> schemas.Collection:
        """POST /collections"""
        self.db.insert_collection(model)
        return model

    def create_item(self, model: schemas.Item, **kwargs) -> schemas.Item:
        """POST /collections/{collectionId}/items"""
        # self.db.insert_item(model)
        # return model
        raise NotImplementedError

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
