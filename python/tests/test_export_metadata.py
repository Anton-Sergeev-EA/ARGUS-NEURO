from __future__ import annotations

import numpy as np
import onnx
from onnx import TensorProto, helper
from onnx.reference import ReferenceEvaluator

from argus.export.export_onnx import strip_export_traces


def test_export_trace_cleanup_preserves_inference_and_provenance() -> None:
    node = helper.make_node("Identity", ["x"], ["y"])
    node.metadata_props.add(
        key="pkg.torch.onnx.stack_trace", value="/build/host/source.py"
    )
    node.metadata_props.add(key="purpose", value="identity-check")
    graph = helper.make_graph(
        [node],
        "test",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 2])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 2])],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 18)])
    sample = np.array([[1.0, -2.0]], dtype=np.float32)
    expected = ReferenceEvaluator(model).run(None, {"x": sample})[0]
    strip_export_traces(model)
    onnx.checker.check_model(model)
    actual = ReferenceEvaluator(model).run(None, {"x": sample})[0]
    np.testing.assert_array_equal(actual, expected)
    assert [(p.key, p.value) for p in model.graph.node[0].metadata_props] == [
        ("purpose", "identity-check")
    ]
