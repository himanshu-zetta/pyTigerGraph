import requests
import json
from requests.auth import HTTPBasicAuth

import unittest
from unittest.mock import patch, Mock, MagicMock

from pyTigerGraph import TigerGraphConnection
from tests.pyTigerGraphUnitTest import make_connection

class TestJWTTokenAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = make_connection()

   
    def requestJWTToken(self):
        # Define the URL
        url = f"{self.conn.host}:{self.conn.gsPort}/gsqlserver/requestjwttoken"
        # Define the data payload
        payload = json.dumps({"lifetime": "1000000000"})
        # Define the headers for the request
        headers = {
            'Content-Type': 'application/json'
        }
        # Make the POST request with basic authentication
        response = requests.post(url, data=payload, headers=headers, auth=(self.conn.username, self.conn.password))
        return response.json()['token']
    
    def test_jwtauth(self):
        dbversion = self.conn.getVer()
        print (f"dbversion from init conn: {dbversion}")
        authheader = self.conn.authHeader
        print (f"authheader from init conn: {authheader}")

        if "3.9" in str(dbversion):
            self.test_jwtauth_3_9()
        elif "4.1" in str(dbversion):
            self.test_jwtauth_4_1_success()
            self.test_jwtauth_4_1_fail()
        else:
            pass

    def test_jwtauth_3_9(self):
        with self.assertRaises(RuntimeError) as context:
            TigerGraphConnection(
                host=self.conn.host,
                jwtToken="fake.JWT.Token"
            )

        # Verify the exception message
        self.assertIn("switch to API token or username/password.", str(context.exception))

    def test_jwtauth_4_1_success(self):
        jwt_token = self.requestJWTToken()

        newconn = TigerGraphConnection(
            host=self.conn.host,
            jwtToken=jwt_token
        )

        authheader = newconn.authHeader
        print (f"authheader from new conn: {authheader}")

        # restpp on port 9000
        dbversion = newconn.getVer()
        print (f"dbversion from new conn: {dbversion}")
        self.assertIn("4.1", str(dbversion))

        # gsql on port 14240
        res = newconn._get(f"{self.conn.host}:{self.conn.gsPort}/gsqlserver/gsql/simpleauth", authMode="token", resKey=None)
        self.assertIn("privileges", res)


    def test_jwtauth_4_1_fail(self):
        with self.assertRaises(RuntimeError) as context:
            TigerGraphConnection(
                host=self.conn.host,
                jwtToken="invalid.JWT.Token"
            )

        # Verify the exception message
        self.assertIn("Please generate new JWT token", str(context.exception))


if __name__ == '__main__':
    # unittest.main()
    suite = unittest.TestSuite()
    suite.addTest(TestJWTTokenAuth("test_jwtauth"))

    runner = unittest.TextTestRunner(verbosity=2, failfast=True) 
    runner.run(suite)