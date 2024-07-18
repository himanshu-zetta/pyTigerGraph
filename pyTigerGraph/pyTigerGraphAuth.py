"""Authentication Functions

The functions on this page authenticate connections and manage TigerGraph credentials.
All functions in this module are called as methods on a link:https://docs.tigergraph.com/pytigergraph/current/core-functions/base[`TigerGraphConnection` object].
"""
import json
import logging
import time
import warnings
from datetime import datetime
from typing import Union

import requests

from pyTigerGraph.pyTigerGraphException import TigerGraphException
from pyTigerGraph.pyTigerGraphGSQL import pyTigerGraphGSQL

logger = logging.getLogger(__name__)


class pyTigerGraphAuth(pyTigerGraphGSQL):

    def getSecrets(self) -> dict:
        """Issues a `SHOW SECRET` GSQL statement and returns the secret generated by that
            statement.
            Secrets are unique strings that serve as credentials when generating authentication tokens.

        Returns:
            A dictionary of `alias: secret_string` pairs.

        Notes:
            This function returns the masked version of the secret. The original value of the secret cannot
            be retrieved after creation.
        """
        logger.info("entry: getSecrets")

        res = self.gsql("""
            USE GRAPH {}
            SHOW SECRET""".format(self.graphname), )
        ret = {}
        lines = res.split("\n")
        i = 0
        while i < len(lines):
            l = lines[i]
            s = ""
            if "- Secret" in l:
                s = l.split(": ")[1]
                i += 1
                l = lines[i]
                if "- Alias" in l:
                    ret[l.split(": ")[1]] = s
            i += 1

        if logger.level == logging.DEBUG:
            logger.debug("return: " + str(ret))
        logger.info("exit: getSecrets")

        return ret
        # TODO Process response, return a dictionary of alias/secret pairs

    def showSecrets(self) -> dict:
        """DEPRECATED

        Use `getSecrets()` instead.
        """
        warnings.warn("The `showSecrets()` function is deprecated; use `getSecrets()` instead.",
            DeprecationWarning)

        return self.getSecrets()

    # TODO getSecret()

    def createSecret(self, alias: str = "", withAlias: bool = False) -> Union[str, dict]:
        """Issues a `CREATE SECRET` GSQL statement and returns the secret generated by that statement.
            Secrets are unique strings that serve as credentials when generating authentication tokens.

        Args:
            alias:
                The alias of the secret. /
                The system will generate a random alias for the secret if the user does not provide
                an alias for that secret. Randomly generated aliases begin with
                `AUTO_GENERATED_ALIAS_` and include a random 7-character string.
            withAlias:
                Return the new secret as an `{"alias": "secret"}` dictionary. This can be useful if
                an alias was not provided, for example if it is auto-generated).

        Returns:
            The secret string.

        Notes:
            Generally, secrets are generated by the database administrator and
            used to generate a token. If you use this function, please consider reviewing your
            internal processes of granting access to TigerGraph instances. Normally, this function
            should not be necessary and should not be executable by generic users.
        """
        logger.info("entry: createSecret")
        if logger.level == logging.DEBUG:
            logger.debug("params: " + self._locals(locals()))

        res = self.gsql("""
            USE GRAPH {}
            CREATE SECRET {} """.format(self.graphname, alias))
        try:
            if ("already exists" in res):
                errorMsg = "The secret "
                if alias != "":
                    errorMsg += "with alias {} ".format(alias)
                errorMsg += "already exists."
                raise TigerGraphException(errorMsg, "E-00001")

            secret = "".join(res).replace('\n', '').split('The secret: ')[1].split(" ")[0].strip()

            if not withAlias:
                if logger.level == logging.DEBUG:
                    logger.debug("return: " + str(secret))
                logger.info("exit: createSecret (withAlias")

                return secret

            if alias:
                ret = {alias: secret}

                if logger.level == logging.DEBUG:
                    logger.debug("return: " + str(ret))
                logger.info("exit: createSecret (alias)")

                return ret

            # Alias was not provided, let's find out the autogenerated one
            masked = secret[:3] + "****" + secret[-3:]
            secs = self.getSecrets()
            for (a, s) in secs.items():
                if s == masked:
                    ret = {a: secret}

                    if logger.level == logging.DEBUG:
                        logger.debug("return: " + str(ret))
                    logger.info("exit: createSecret")

                    return ret

        except:
            raise

    def dropSecret(self, alias: Union[str, list], ignoreErrors: bool = True) -> str:
        """Drops a secret.
            See https://docs.tigergraph.com/tigergraph-server/current/user-access/managing-credentials#_drop_a_secret

            Args:
                alias:
                    One or more alias(es) of secret(s).
                ignoreErrors:
                    Ignore errors arising from trying to drop non-existent secrets.

            Raises:
                `TigerGraphException` if a non-existent secret is attempted to be dropped (unless
                `ignoreErrors` is `True`). Re-raises other exceptions.
        """
        logger.info("entry: dropSecret")
        if logger.level == logging.DEBUG:
            logger.debug("params: " + self._locals(locals()))

        if isinstance(alias, str):
            alias = [alias]
        cmd = """
            USE GRAPH {}""".format(self.graphname)
        for a in alias:
            cmd += """
                DROP SECRET {}""".format(a)
        res = self.gsql(cmd)
        if "Failed to drop secrets" in res and not ignoreErrors:
            raise TigerGraphException(res)

        if logger.level == logging.DEBUG:
            logger.debug("return: " + str(res))
        logger.info("exit: dropSecret")

        return res

    def getToken(self, secret: str = None, setToken: bool = True, lifetime: int = None) -> Union[tuple, str]:
        """Requests an authorization token.

        This function returns a token only if REST++ authentication is enabled. If not, an exception
        will be raised.
        See https://docs.tigergraph.com/admin/admin-guide/user-access-management/user-privileges-and-authentication#rest-authentication

        Args:
            secret (str, Optional):
                The secret (string) generated in GSQL using `CREATE SECRET`.
                See https://docs.tigergraph.com/tigergraph-server/current/user-access/managing-credentials#_create_a_secret
            setToken (bool, Optional):
                Set the connection's API token to the new value (default: `True`).
            lifetime (int, Optional):
                Duration of token validity (in seconds, default 30 days = 2,592,000 seconds).

        Returns:
            If your TigerGraph instance is running version 3.10, the return value is 
            a tuple of `(<token>, <expiration_timestamp_unixtime>, <expiration_timestamp_ISO8601>)`.
            The return value can be ignored, as the token is automatically set for the connection after this call.

            If your TigerGraph instance is running version 4.0, the return value is a tuple of `(<token>, <expiration_timestamp_with_local_time>).

            [NOTE]
            The expiration timestamp's time zone might be different from your computer's local time
            zone.

        Raises:
            `TigerGraphException` if REST++ authentication is not enabled or if an authentication
            error occurred.

        Endpoint:
            - `POST /requesttoken` (In TigerGraph versions 3.x)
                See https://docs.tigergraph.com/tigergraph-server/current/api/built-in-endpoints#_request_a_token
            - `POST /gsql/v1/tokens` (In TigerGraph versions 4.x)
        """
        logger.info("entry: getToken")
        if logger.level == logging.DEBUG:
            logger.debug("params: " + self._locals(locals()))

        s, m, i = (0, 0, 0)
        res = {}
        if self.version:
            s, m, i = self.version.split(".")
        success = False

        if secret and (int(s) < 3 or (int(s) == 3 and int(m) < 5)):
            try:
                # /gsql/v1/tokens endpoint only supported on version >=4.1 and replaced /requesttoken
                _json = {"secret": secret, "graph": self.graphname}
                if lifetime:
                    _json["lifetime"] = str(lifetime)
                res = requests.request("POST", self.gsUrl +
                    "/gsql/v1/tokens", verify=False, json=_json, headers={"X-User-Agent": "pyTigerGraph"})
                
                # if /gsql/v1/tokens endpoint doesn't exist then try old endpoint
                if res.status_code == 404:
                    res = requests.request("GET", self.restppUrl +
                        "/requesttoken?secret=" + secret +
                        ("&lifetime=" + str(lifetime) if lifetime else ""), verify=False)
                res = json.loads(res.text)

                if not res["error"]:
                    success = True
            except Exception as e:
                raise e
        elif not(success) and not(secret):
            res = self._post(self.restppUrl+"/requesttoken", authMode="pwd", data=str({"graph": self.graphname}), resKey="results")
            success = True
        elif not(success) and (int(s) < 3 or (int(s) == 3 and int(m) < 5)):
            raise TigerGraphException("Cannot request a token with username/password for versions < 3.5.")


        if not success:
            try:
                data = {"secret": secret}

                if lifetime:
                    data["lifetime"] = str(lifetime)

                res = json.loads(requests.post(self.restppUrl + "/requesttoken",
                    data=json.dumps(data), verify=False).text)
            except Exception as e:
                raise e

        
        if not res.get("error"):
            if setToken:
                self.apiToken = res["token"]
                self.authHeader = {'Authorization': "Bearer " + self.apiToken}
            else:
                self.apiToken = None
                self.authHeader = {'Authorization': 'Basic {0}'.format(self.base64_credential)}
            
            if res.get("expiration"):
                # On >=4.1 the format for the date of expiration changed. Convert back to old format
                if self._versionGreaterThan4_0():
                    ret = res["token"], res.get("expiration")
                else:
                    ret = res["token"], res.get("expiration"), \
                        datetime.utcfromtimestamp(float(res.get("expiration"))).strftime('%Y-%m-%d %H:%M:%S')
            else:
                ret = res["token"]

            if logger.level == logging.DEBUG:
                logger.debug("return: " + str(ret))
            logger.info("exit: parseVertices")

            return ret

        if "Endpoint is not found from url = /requesttoken" in res["message"]:
            raise TigerGraphException("REST++ authentication is not enabled, can't generate token.",
                None)
        raise TigerGraphException(res["message"], (res["code"] if "code" in res else None))

    def refreshToken(self, secret: str, token: str = "", lifetime: int = None) -> tuple:
        """Extends a token's lifetime.

        This function works only if REST++ authentication is enabled. If not, an exception will be
        raised.
        See https://docs.tigergraph.com/admin/admin-guide/user-access-management/user-privileges-and-authentication#rest-authentication

        Args:
            secret:
                The secret (string) generated in GSQL using `CREATE SECRET`.
                See https://docs.tigergraph.com/tigergraph-server/current/user-access/managing-credentials#_create_a_secret
            token:
                The token requested earlier. If not specified, refreshes current connection's token.
            lifetime:
                Duration of token validity (in seconds, default 30 days = 2,592,000 seconds) from
                current system timestamp.

        Returns:
            A tuple of `(<token>, <expiration_timestamp_unixtime>, <expiration_timestamp_ISO8601>)`.
            The return value can be ignored. /
            New expiration timestamp will be now + lifetime seconds, _not_ current expiration
            timestamp + lifetime seconds.

            [NOTE]
            The expiration timestamp's time zone might be different from your computer's local time
            zone.


        Raises:
            `TigerGraphException` if REST++ authentication is not enabled, if an authentication error
            occurs, or if calling while using TigerGraph 4.x.

        Note:
            Not avaliable on TigerGraph version 4.x

        Endpoint:
            - `PUT /requesttoken`
                See https://docs.tigergraph.com/tigergraph-server/current/api/built-in-endpoints#_refresh_a_token
        TODO Rework lifetime parameter handling the same as in getToken()
        """
        logger.info("entry: refreshToken")
        if logger.level == logging.DEBUG:
            logger.debug("params: " + self._locals(locals()))

        s, m, i = (0, 0, 0)
        res = {}
        if self.version:
            s, m, i = self.version.split(".")
        success = False

        if not token:
            token = self.apiToken

        if self._versionGreaterThan4_0():
            logger.info("exit: refreshToken")
            raise TigerGraphException("Refreshing tokens is only supported on versions of TigerGraph <= 4.0.0.", 0)

        if int(s) < 3 or (int(s) == 3 and int(m) < 5):
            if self.useCert and self.certPath:
                res = json.loads(requests.request("PUT", self.restppUrl + "/requesttoken?secret=" +
                    secret + "&token=" + token + ("&lifetime=" + str(lifetime) if lifetime else ""),
                    verify=False).text)
            else:
                res = json.loads(requests.request("PUT", self.restppUrl + "/requesttoken?secret=" +
                    secret + "&token=" + token + ("&lifetime=" + str(lifetime) if lifetime else "")
                    ).text)
            if not res["error"]:
                success = True
            if "Endpoint is not found from url = /requesttoken" in res["message"]:
                raise TigerGraphException("REST++ authentication is not enabled, can't refresh token.",
                    None)

        if not success:
            data = {"secret": secret, "token": token}
            if lifetime:
                data["lifetime"] = str(lifetime)
            if self.useCert is True and self.certPath is not None:
                res = json.loads(requests.post(self.restppUrl + "/requesttoken",
                    data=json.dumps(data), verify=False).text)
            else:
                res = json.loads(requests.post(self.restppUrl + "/requesttoken",
                    data=json.dumps(data)).text)
            if not res["error"]:
                success = True
            if "Endpoint is not found from url = /requesttoken" in res["message"]:
                raise TigerGraphException("REST++ authentication is not enabled, can't refresh token.",
                    None)

        if success:
            exp = time.time() + res["expiration"]
            ret = res["token"], int(exp), \
                datetime.utcfromtimestamp(exp).strftime('%Y-%m-%d %H:%M:%S')

            if logger.level == logging.DEBUG:
                logger.debug("return: " + str(ret))
            logger.info("exit: refreshToken")

            return ret

        raise TigerGraphException(res["message"], (res["code"] if "code" in res else None))

    def deleteToken(self, secret, token=None, skipNA=True) -> bool:
        """Deletes a token.

        This function works only if REST++ authentication is enabled. If not, an exception will be
        raised.
        See https://docs.tigergraph.com/tigergraph-server/current/user-access/enabling-user-authentication#_enable_restpp_authentication

        Args:
            secret:
                The secret (string) generated in GSQL using `CREATE SECRET`.
                See https://docs.tigergraph.com/tigergraph-server/current/user-access/managing-credentials#_create_a_secret
            token:
                The token requested earlier. If not specified, deletes current connection's token,
                so be careful.
            skipNA:
                Don't raise an exception if the specified token does not exist.

        Returns:
            `True`, if deletion was successful, or if the token did not exist but `skipNA` was
            `True`.

        Raises:
            `TigerGraphException` if REST++ authentication is not enabled or an authentication error
            occurred, for example if the specified token does not exist.

        Endpoint:
            - `DELETE /requesttoken` (In TigerGraph version 3.x)
                See https://docs.tigergraph.com/tigergraph-server/current/api/built-in-endpoints#_delete_a_token
            - `DELETE /gsql/v1/tokens` (In TigerGraph version 4.x)
        """
        logger.info("entry: deleteToken")
        if logger.level == logging.DEBUG:
            logger.debug("params: " + self._locals(locals()))

        s, m, i = (0, 0, 0)
        res = {}
        if self.version:
            s, m, i = self.version.split(".")
        success = False

        if not token:
            token = self.apiToken

        if int(s) < 3 or (int(s) == 3 and int(m) < 5):
            if self.useCert is True and self.certPath is not None:
                if self._versionGreaterThan4_0():
                    res = requests.request("DELETE", self.gsUrl +
                    "/gsql/v1/tokens", verify=False, json={"secret": secret, "token": token},
                      headers={"X-User-Agent": "pyTigerGraph"})
                    res = json.loads(res.text)
                else:
                    res = json.loads(
                        requests.request("DELETE",
                        self.restppUrl + "/requesttoken?secret=" + secret + "&token=" + token,
                        verify=False).text)
            else:
                if self._versionGreaterThan4_0():
                    res = requests.request("DELETE", self.gsUrl +
                    "/gsql/v1/tokens", verify=False, json={"tokens": token},
                      headers={"X-User-Agent": "pyTigerGraph"})
                    res = json.loads(res.text)
                else:
                    res = json.loads(
                        requests.request("DELETE",
                            self.restppUrl + "/requesttoken?secret=" + secret + "&token=" + token).text)
            if not res["error"]:
                success = True

        if not success:
            data = {"secret": secret, "token": token}
            if self.useCert is True and self.certPath is not None:
                res = json.loads(requests.delete(self.restppUrl + "/requesttoken",
                    data=json.dumps(data)).text)
            else:
                if self._versionGreaterThan4_0():
                    res = requests.request("DELETE", self.gsUrl +
                    "/gsql/v1/tokens", verify=False, data=json.dumps(data),
                      headers={"X-User-Agent": "pyTigerGraph"})
                    res = json.loads(res.text)
                else:
                    res = json.loads(requests.delete(self.restppUrl + "/requesttoken",
                        data=json.dumps(data), verify=False).text)

        if "Endpoint is not found from url = /requesttoken" in res["message"]:
            raise TigerGraphException("REST++ authentication is not enabled, can't delete token.",
                None)

        if not res["error"]:
            if logger.level == logging.DEBUG:
                logger.debug("return: " + str(True))
            logger.info("exit: deleteToken")

            return True

        if res["code"] == "REST-3300" and skipNA:
            if logger.level == logging.DEBUG:
                logger.debug("return: " + str(True))
            logger.info("exit: parseVertices")

            return True

        raise TigerGraphException(res["message"], (res["code"] if "code" in res else None))
