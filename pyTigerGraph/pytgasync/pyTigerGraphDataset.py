"""Data Ingestion Functions

Ingest stock datasets into a TigerGraph database.
All functions in this module are called as methods on a link:https://docs.tigergraph.com/pytigergraph/current/core-functions/base[`TigerGraphConnection` object]. 
"""

import logging

from pyTigerGraph.common.dataset import _parse_ingest_dataset
from pyTigerGraph.pytgasync.datasets import AsyncDatasets
from pyTigerGraph.pytgasync.pyTigerGraphAuth import AsyncPyTigerGraphAuth


logger = logging.getLogger(__name__)


class AsyncPyTigerGraphDataset(AsyncPyTigerGraphAuth):
    async def ingestDataset(
        self,
        dataset: AsyncDatasets,
        cleanup: bool = True,
        getToken: bool = False
    ) -> None:
        """Ingest a stock dataset to a TigerGraph database.

        Args:
            dataset (Datasets):
                A Datasets object as `pyTigerGraph.datasets.Datasets`.
            cleanup (bool, optional):
                Whether or not to remove local artifacts downloaded by `Datasets`
                after ingestion is done. Defaults to True.
            getToken (bool, optional):
                Whether or not to get auth token from the database. This is required
                when auth token is enabled for the database. Defaults to False.
        """
        logger.info("entry: ingestDataset")
        if logger.level == logging.DEBUG:
            logger.debug("params: " + self._locals(locals()))

        if not dataset.ingest_ready:
            raise Exception("This dataset is not ingestable.")

        print("---- Checking database ----", flush=True)
        if await self.check_exist_graphs(dataset.name):
            # self.gsql("USE GRAPH {}\nDROP JOB ALL\nDROP GRAPH {}".format(
            #     dataset.name, dataset.name
            # ))
            self.graphname = dataset.name
            if getToken:
                await self.getToken(await self.createSecret())
            print(
                "A graph with name {} already exists in the database. "
                "Skip ingestion.".format(dataset.name)
            )
            print("Graph name is set to {} for this connection.".format(dataset.name))
            return

        print("---- Creating graph ----", flush=True)
        resp = await dataset.create_graph(self)
        print(resp, flush=True)
        if "Failed" in resp:
            return

        print("---- Creating schema ----", flush=True)
        resp = await dataset.create_schema(self)
        print(resp, flush=True)
        if "Failed" in resp:
            return

        print("---- Creating loading job ----", flush=True)
        resp = await dataset.create_load_job(self)
        print(resp, flush=True)
        if "Failed" in resp:
            return

        print("---- Ingesting data ----", flush=True)
        self.graphname = dataset.name
        if getToken:
            secret = await self.createSecret()
            await self.getToken(secret)

        responses = []
        for resp in await dataset.run_load_job(self):
            responses.append(resp)

        _parse_ingest_dataset(responses, cleanup, dataset)

        print("---- Finished ingestion ----", flush=True)
        logger.info("exit: ingestDataset")

    async def check_exist_graphs(self, name: str) -> bool:
        "NO DOC"
        resp = await self.gsql("ls")
        return "Graph {}".format(name) in resp
