import io
import unittest
from queue import Queue
from threading import Event

import pandas as pd
import torch
from pandas.testing import assert_frame_equal
from pyTigerGraph import TigerGraphConnection
from pyTigerGraph.gds.dataloaders import BaseLoader
from torch.testing import assert_close as assert_close_torch
from torch_geometric.data import Data as pygData


class TestGDSBaseLoader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = TigerGraphConnection(host="http://35.230.92.92", graphname="Cora")
        cls.loader = BaseLoader(conn)
        # conn.gsql("drop query all")

    def test_get_schema(self):
        self.assertDictEqual(
            self.loader._v_schema,
            {
                "Paper": {
                    "x": "INT",
                    "y": "INT",
                    "train_mask": "BOOL",
                    "val_mask": "BOOL",
                    "test_mask": "BOOL",
                    "id": "INT",
                }
            },
        )
        self.assertDictEqual(
            self.loader._e_schema,
            {
                "Cite": {
                    "time": "INT",
                    "is_train": "BOOL"
                }
            },
        )

    def test_validate_vertex_attributes(self):
        # Empty input
        self.assertListEqual(self.loader._validate_vertex_attributes(None), [])
        self.assertListEqual(self.loader._validate_vertex_attributes([]), [])
        self.assertListEqual(self.loader._validate_vertex_attributes({}), [])
        self.assertDictEqual(self.loader._validate_vertex_attributes(None, True), {})
        self.assertDictEqual(self.loader._validate_vertex_attributes([], True), {})
        self.assertDictEqual(self.loader._validate_vertex_attributes({}, True), {})
        # Extra spaces
        self.assertListEqual(
            self.loader._validate_vertex_attributes(["x ", " y"]), ["x", "y"]
        )
        self.assertDictEqual(
            self.loader._validate_vertex_attributes({"Paper": ["x ", " y"]}, True), 
            {"Paper": ["x", "y"]}
        )
        # Wrong input
        with self.assertRaises(ValueError):
            self.loader._validate_vertex_attributes("x")
        with self.assertRaises(ValueError):
            self.loader._validate_vertex_attributes(["nonexist"])
        with self.assertRaises(ValueError):
            self.loader._validate_vertex_attributes({"Paper": ["nonexist"]})
        with self.assertRaises(ValueError):
            self.loader._validate_vertex_attributes(1)
        with self.assertRaises(ValueError):
            self.loader._validate_vertex_attributes(["x"], is_hetero = True)
        with self.assertRaises(ValueError):
            self.loader._validate_vertex_attributes({"Paper": ["x"]}, is_hetero = False)    

    def test_validate_edge_attributes(self):
        # Empty input
        self.assertListEqual(self.loader._validate_edge_attributes(None), [])
        self.assertListEqual(self.loader._validate_edge_attributes([]), [])
        self.assertListEqual(self.loader._validate_edge_attributes({}), [])
        self.assertDictEqual(self.loader._validate_edge_attributes(None, True), {})
        self.assertDictEqual(self.loader._validate_edge_attributes([], True), {})
        self.assertDictEqual(self.loader._validate_edge_attributes({}, True), {})
        # Extra spaces
        self.assertListEqual(
            self.loader._validate_edge_attributes(["time ", "is_train"]), ["time", "is_train"]
        )
        self.assertDictEqual(
            self.loader._validate_edge_attributes({"Cite": ["time ", "is_train"]}, True), 
            {"Cite": ["time", "is_train"]}
        )
        # Wrong input
        with self.assertRaises(ValueError):
            self.loader._validate_edge_attributes("time")
        with self.assertRaises(ValueError):
            self.loader._validate_edge_attributes(["nonexist"])
        with self.assertRaises(ValueError):
            self.loader._validate_edge_attributes({"Cite": ["nonexist"]})
        with self.assertRaises(ValueError):
            self.loader._validate_edge_attributes(1)
        with self.assertRaises(ValueError):
            self.loader._validate_edge_attributes(["time"], is_hetero = True)
        with self.assertRaises(ValueError):
            self.loader._validate_edge_attributes({"Cite": ["time"]}, is_hetero = False)  

    def test_read_vertex_bytes(self):
        read_task_q = Queue()
        data_q = Queue(4)
        exit_event = Event()
        raw = "99,1 0 0 1 ,1,0,1\n8,1 0 0 1 ,1,1,1\n".encode("utf-8")
        read_task_q.put(raw)
        read_task_q.put(None)
        self.loader._read_data(
            exit_event,
            read_task_q,
            data_q,
            "vertex_bytes",
            "dataframe",
            ["x"],
            ["y"],
            ["train_mask", "is_seed"],
            {"x": "int", "y": "int", "train_mask": "bool", "is_seed": "bool"},
        )
        data = data_q.get()
        truth = pd.read_csv(
            io.BytesIO(raw),
            header=None,
            names=["vid", "x", "y", "train_mask", "is_seed"],
        )
        assert_frame_equal(data, truth)
        data = data_q.get()
        self.assertIsNone(data)

    def test_read_edge_bytes(self):
        read_task_q = Queue()
        data_q = Queue(4)
        exit_event = Event()
        raw = "1,2,0.1,2021,1,0\n2,1,1.5,2020,0,1\n".encode("utf-8")
        read_task_q.put(raw)
        read_task_q.put(None)
        self.loader._read_data(
            exit_event, read_task_q, data_q, "edge_bytes", "dataframe", [], [], [], {},
            ["x", "time"], ["y"], ["is_train"], 
            {"x": "float", "time": "int", "y": "int", "is_train": "bool"} 
        )
        data = data_q.get()
        truth = pd.read_csv(io.BytesIO(raw), header=None, 
            names=["source", "target", "x", "time", "y", "is_train"])
        assert_frame_equal(data, truth)
        data = data_q.get()
        self.assertIsNone(data)

    def test_read_graph_bytes_out_df(self):
        read_task_q = Queue()
        data_q = Queue(4)
        exit_event = Event()
        raw = (
            "99,1 0 0 1 ,1,0,1\n8,1 0 0 1 ,1,1,1\n".encode("utf-8"),
            "1,2,0.1,2021,1,0\n2,1,1.5,2020,0,1\n".encode("utf-8")
        )
        read_task_q.put(raw)
        read_task_q.put(None)
        self.loader._read_data(
            exit_event,
            read_task_q,
            data_q,
            "graph_bytes",
            "dataframe",
            ["x"],
            ["y"],
            ["train_mask", "is_seed"],
            {"x": "int", "y": "int", "train_mask": "bool", "is_seed": "bool"},
            ["x", "time"], ["y"], ["is_train"], 
            {"x": "float", "time": "int", "y": "int", "is_train": "bool"} 
        )
        data = data_q.get()
        vertices = pd.read_csv(
            io.BytesIO(raw[0]),
            header=None,
            names=["vid", "x", "y", "train_mask", "is_seed"],
        )
        edges = pd.read_csv(io.BytesIO(raw[1]), header=None, 
            names=["source", "target", "x", "time", "y", "is_train"])
        assert_frame_equal(data[0], vertices)
        assert_frame_equal(data[1], edges)
        data = data_q.get()
        self.assertIsNone(data)

    def test_read_graph_bytes_out_pyg(self):
        read_task_q = Queue()
        data_q = Queue(4)
        exit_event = Event()
        raw = (
            "99,1 0 0 1 ,1,0,Alex,1\n8,1 0 0 1 ,1,1,Bill,1\n".encode("utf-8"),
            "99,8,0.1,2021,1,0\n8,99,1.5,2020,0,1\n".encode("utf-8")
        )
        read_task_q.put(raw)
        read_task_q.put(None)
        self.loader._read_data(
            exit_event,
            read_task_q,
            data_q,
            "graph_bytes",
            "pyg",
            ["x"],
            ["y"],
            ["train_mask", "name", "is_seed"],
            {
                "x": "int",
                "y": "int",
                "train_mask": "bool",
                "name": "string",
                "is_seed": "bool",
            },
            ["x", "time"], ["y"], ["is_train"], 
            {"x": "double", "time": "int", "y": "int", "is_train": "bool"} 
        )
        data = data_q.get()
        self.assertIsInstance(data, pygData)
        assert_close_torch(data["edge_index"], torch.tensor([[0, 1], [1, 0]]))
        assert_close_torch(data["edge_feat"], 
            torch.tensor([[0.1, 2021], [1.5, 2020]], dtype=torch.double))
        assert_close_torch(data["edge_label"], torch.tensor([1, 0]))
        assert_close_torch(data["is_train"], torch.tensor([False, True]))
        assert_close_torch(data["x"], torch.tensor([[1, 0, 0, 1], [1, 0, 0, 1]]))
        assert_close_torch(data["y"], torch.tensor([1, 1]))
        assert_close_torch(data["train_mask"], torch.tensor([False, True]))
        assert_close_torch(data["is_seed"], torch.tensor([True, True]))
        self.assertListEqual(data["name"], ["Alex", "Bill"])
        data = data_q.get()
        self.assertIsNone(data)

    def test_read_graph_bytes_no_attr(self):
        read_task_q = Queue()
        data_q = Queue(4)
        exit_event = Event()
        raw = ("99,1\n8,1\n".encode("utf-8"), "99,8\n8,99\n".encode("utf-8"))
        read_task_q.put(raw)
        read_task_q.put(None)
        self.loader._read_data(
            exit_event,
            read_task_q,
            data_q,
            "graph_bytes",
            "pyg",
            [],
            [],
            ["is_seed"],
            {
                "x": "int",
                "y": "int",
                "train_mask": "bool",
                "name": "string",
                "is_seed": "bool",
            },
            [],
            [],
            [],
            {}
        )
        data = data_q.get()
        self.assertIsInstance(data, pygData)
        assert_close_torch(data["edge_index"], torch.tensor([[0, 1], [1, 0]]))
        assert_close_torch(data["is_seed"], torch.tensor([True, True]))
        data = data_q.get()
        self.assertIsNone(data)


if __name__ == "__main__":
    suite = unittest.TestSuite()
    suite.addTest(TestGDSBaseLoader("test_get_schema"))
    suite.addTest(TestGDSBaseLoader("test_validate_vertex_attributes"))
    suite.addTest(TestGDSBaseLoader("test_validate_edge_attributes"))
    suite.addTest(TestGDSBaseLoader("test_read_vertex_bytes"))
    suite.addTest(TestGDSBaseLoader("test_read_edge_bytes"))
    suite.addTest(TestGDSBaseLoader("test_read_graph_bytes_out_df"))
    suite.addTest(TestGDSBaseLoader("test_read_graph_bytes_out_pyg"))
    suite.addTest(TestGDSBaseLoader("test_read_graph_bytes_no_attr"))
    runner = unittest.TextTestRunner(verbosity=2, failfast=True)
    runner.run(suite)
