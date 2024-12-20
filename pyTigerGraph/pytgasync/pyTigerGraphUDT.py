"""User Defined Tuple (UDT) Functions.

The functions on this page retrieve information about user-defined tuples (UDT) for the graph.
All functions in this module are called as methods on a link:https://docs.tigergraph.com/pytigergraph/current/core-functions/base[`TigerGraphConnection` object].
"""

import logging

from pyTigerGraph.pytgasync.pyTigerGraphSchema import AsyncPyTigerGraphSchema
# from pyTigerGraph.pyTigerGraphUDT import pyTigerGraphUDT

logger = logging.getLogger(__name__)


class AsyncPyTigerGraphUDT(AsyncPyTigerGraphSchema):

    async def getUDTs(self) -> list:
        """Returns the list of User-Defined Tuples (names only).

        For information on UDTs see xref:gsql-ref:ddl-and-loading:system-and-language-basics.adoc#typedef-tuple[User-Defined Tuple]

        Returns:
            The list of names of UDTs (defined in the global scope, i.e. not in queries).
        """
        logger.info("entry: getUDTs")

        ret = []
        for udt in await self._getUDTs():
            ret.append(udt["name"])

        if logger.level == logging.DEBUG:
            logger.debug("return: " + str(ret))
        logger.info("exit: getUDTs")

        return ret

    async def getUDT(self, udtName: str) -> list:
        """Returns the details of a specific User-Defined Tuple (defined in the global scope).

        For information on UDTs see xref:gsql-ref:ddl-and-loading:system-and-language-basics.adoc#typedef-tuple[User-Defined Tuple]

        Args:
            udtName:
                The name of the User-Defined Tuple.

        Returns:
            The metadata (the details of the fields) of the UDT.

        """
        logger.info("entry: getUDT")
        if logger.level == logging.DEBUG:
            logger.debug("params: " + self._locals(locals()))

        for udt in await self._getUDTs():
            if udt["name"] == udtName:
                ret = udt["fields"]

                if logger.level == logging.DEBUG:
                    logger.debug("return: " + str(ret))
                logger.info("exit: getUDT (found)")

                return ret

        if logger.level == logging.DEBUG:
            logger.warning("UDT `" + udtName + "` was not found")
        logger.info("exit: getUDT (not found)")

        return []  # UDT was not found
