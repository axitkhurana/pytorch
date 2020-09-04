import os
import sys

import torch
from torch.testing import FileCheck
from enum import Enum
from typing import Any, List

# Make the helper files in test/ importable
pytorch_test_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(pytorch_test_dir)
from torch.testing._internal.jit_utils import JitTestCase

if __name__ == '__main__':
    raise RuntimeError("This test file is not meant to be run directly, use:\n\n"
                       "\tpython test/test_jit.py TESTNAME\n\n"
                       "instead.")

class TestEnum(JitTestCase):
    def setUp(self):
        super().setUp()
        self.saved_enum_env_var = os.environ.get("EXPERIMENTAL_ENUM_SUPPORT", None)
        os.environ["EXPERIMENTAL_ENUM_SUPPORT"] = "1"

    def tearDown(self):
        super().tearDown()
        if self.saved_enum_env_var:
            os.environ["EXPERIMENTAL_ENUM_SUPPORT"] = self.saved_enum_env_var

    def test_enum_value_types(self):
        global IntEnum

        class IntEnum(Enum):
            FOO = 1
            BAR = 2

        global FloatEnum

        class FloatEnum(Enum):
            FOO = 1.2
            BAR = 2.3

        global StringEnum

        class StringEnum(Enum):
            FOO = "foo as in foo bar"
            BAR = "bar as in foo bar"

        @torch.jit.script
        def supported_enum_types(a: IntEnum, b: FloatEnum, c: StringEnum):
            return (a.name, b.name, c.name)

        FileCheck() \
            .check("IntEnum") \
            .check("FloatEnum") \
            .check("StringEnum") \
            .run(str(supported_enum_types.graph))

        global TensorEnum

        class TensorEnum(Enum):
            FOO = torch.tensor(0)
            BAR = torch.tensor(1)

        def unsupported_enum_types(a: TensorEnum):
            return a.name

        with self.assertRaisesRegex(RuntimeError, "Cannot create Enum with value type 'Tensor'"):
            torch.jit.script(unsupported_enum_types)

    def test_enum_comp(self):
        global Color

        class Color(Enum):
            RED = 1
            GREEN = 2

        @torch.jit.script
        def enum_comp(x: Color, y: Color) -> bool:
            return x == y

        FileCheck().check("aten::eq").run(str(enum_comp.graph))

        self.assertEqual(enum_comp(Color.RED, Color.RED), True)
        self.assertEqual(enum_comp(Color.RED, Color.GREEN), False)

    def test_enum_comp_diff_classes(self):
        global Foo, Bar

        class Foo(Enum):
            ITEM1 = 1
            ITEM2 = 2

        class Bar(Enum):
            ITEM1 = 1
            ITEM2 = 2

        @torch.jit.script
        def enum_comp(x: Foo) -> bool:
            return x == Bar.ITEM1

        FileCheck() \
            .check("prim::Constant") \
            .check_same("Bar.ITEM1") \
            .check("aten::eq") \
            .run(str(enum_comp.graph))

        self.assertEqual(enum_comp(Foo.ITEM1), False)

    def test_heterogenous_value_type_enum_error(self):
        global Color

        class Color(Enum):
            RED = 1
            GREEN = "green"

        def enum_comp(x: Color, y: Color) -> bool:
            return x == y

        with self.assertRaisesRegex(RuntimeError, "Could not unify type list"):
            torch.jit.script(enum_comp)

    def test_enum_name(self):
        global Color

        class Color(Enum):
            RED = 1
            GREEN = 2

        @torch.jit.script
        def enum_name(x: Color) -> str:
            return x.name

        FileCheck() \
            .check("Color") \
            .check_next("prim::EnumName") \
            .check_next("return") \
            .run(str(enum_name.graph))

        self.assertEqual(enum_name(Color.RED), Color.RED.name)
        self.assertEqual(enum_name(Color.GREEN), Color.GREEN.name)

    def test_enum_value(self):
        global Color

        class Color(Enum):
            RED = 1
            GREEN = 2

        @torch.jit.script
        def enum_value(x: Color) -> int:
            return x.value

        FileCheck() \
            .check("Color") \
            .check_next("prim::EnumValue") \
            .check_next("return") \
            .run(str(enum_value.graph))

        self.assertEqual(enum_value(Color.RED), Color.RED.value)
        self.assertEqual(enum_value(Color.GREEN), Color.GREEN.value)

    def test_enum_as_const(self):
        global Color

        class Color(Enum):
            RED = 1
            GREEN = 2

        @torch.jit.script
        def enum_const(x: Color) -> bool:
            return x == Color.RED

        FileCheck() \
            .check("prim::Constant[value=__torch__.jit.test_enum.Color.RED]") \
            .check_next("aten::eq") \
            .check_next("return") \
            .run(str(enum_const.graph))

        self.assertEqual(enum_const(Color.RED), True)
        self.assertEqual(enum_const(Color.GREEN), False)

    def test_non_existent_enum_value(self):
        global Color

        class Color(Enum):
            RED = 1
            GREEN = 2

        def enum_const(x: Color) -> bool:
            if x == Color.PURPLE:
                return True
            else:
                return False

        with self.assertRaisesRegexWithHighlight(RuntimeError, "has no attribute 'PURPLE'", "Color.PURPLE"):
            torch.jit.script(enum_const)

    def test_enum_ivalue_type(self):
        global Color

        class Color(Enum):
            RED = 1
            GREEN = 2

        @torch.jit.script
        def is_color_enum(x: Any):
            return isinstance(x, Color)

        FileCheck() \
            .check("prim::isinstance[types=[Enum<__torch__.jit.test_enum.Color>]]") \
            .check_next("return") \
            .run(str(is_color_enum.graph))

        self.assertEqual(is_color_enum(Color.RED), True)
        self.assertEqual(is_color_enum(Color.GREEN), True)
        self.assertEqual(is_color_enum(1), False)

    def test_closed_over_enum_constant(self):
        global Color

        class Color(Enum):
            RED = 1
            GREEN = 2

        a = Color

        @torch.jit.script
        def closed_over_aliased_type():
            return a.RED.value

        FileCheck() \
            .check("prim::Constant[value={}]".format(a.RED.value)) \
            .check_next("return") \
            .run(str(closed_over_aliased_type.graph))

        self.assertEqual(closed_over_aliased_type(), Color.RED.value)

        b = Color.RED

        @torch.jit.script
        def closed_over_aliased_value():
            return b.value

        FileCheck() \
            .check("prim::Constant[value={}]".format(b.value)) \
            .check_next("return") \
            .run(str(closed_over_aliased_value.graph))

        self.assertEqual(closed_over_aliased_value(), Color.RED.value)

    def test_enum_as_module_attribute(self):
        global Color

        class Color(Enum):
            RED = 1
            GREEN = 2

        class TestModule(torch.nn.Module):
            def __init__(self, e: Color):
                super(TestModule, self).__init__()
                self.e = e

            def forward(self):
                return self.e.value

        m = TestModule(Color.RED)
        scripted = torch.jit.script(m)

        FileCheck() \
            .check("TestModule") \
            .check_next("Color") \
            .check_same("prim::GetAttr[name=\"e\"]") \
            .check_next("prim::EnumValue") \
            .check_next("return") \
            .run(str(scripted.graph))

        self.assertEqual(scripted(), Color.RED.value)

    def test_enum_return(self):
        global Color

        class Color(Enum):
            RED = 1
            GREEN = 2

        @torch.jit.script
        def return_enum(cond: bool):
            if cond:
                return Color.RED
            else:
                return Color.GREEN

        self.assertEqual(return_enum(True), Color.RED)
        self.assertEqual(return_enum(False), Color.GREEN)

    def test_enum_module_return(self):
        global Color

        class Color(Enum):
            RED = 1
            GREEN = 2

        class TestModule(torch.nn.Module):
            def __init__(self, e: Color):
                super(TestModule, self).__init__()
                self.e = e

            def forward(self):
                return self.e

        m = TestModule(Color.RED)
        scripted = torch.jit.script(m)

        FileCheck() \
            .check("TestModule") \
            .check_next("Color") \
            .check_same("prim::GetAttr[name=\"e\"]") \
            .check_next("return") \
            .run(str(scripted.graph))

        self.assertEqual(scripted(), Color.RED)


    def test_enum_iterate(self):
        global Color

        class Color(Enum):
            RED = 1
            GREEN = 2
            BLUE = 3

        def iterate_enum(x: Color):
            res: List[int] = []
            for e in Color:
                if e != x:
                    res.append(e.value)
            return res

        scripted = torch.jit.script(iterate_enum)

        FileCheck() \
            .check("Enum<__torch__.jit.test_enum.Color>[]") \
            .check_same("Color.RED") \
            .check_same("Color.GREEN") \
            .check_same("Color.BLUE") \
            .run(str(scripted.graph))

        # PURPLE always appear last because we follow Python's Enum definition order.
        self.assertEqual(scripted(Color.RED), [Color.GREEN.value, Color.BLUE.value])
        self.assertEqual(scripted(Color.GREEN), [Color.RED.value, Color.BLUE.value])


# Tests that Enum support features are properly guarded before they are mature.
class TestEnumFeatureGuard(JitTestCase):
    def setUp(self):
        super().setUp()
        self.saved_enum_env_var = os.environ.get("EXPERIMENTAL_ENUM_SUPPORT", None)
        if self.saved_enum_env_var:
            del os.environ["EXPERIMENTAL_ENUM_SUPPORT"]

    def tearDown(self):
        super().tearDown()
        if self.saved_enum_env_var:
            os.environ["EXPERIMENTAL_ENUM_SUPPORT"] = self.saved_enum_env_var

    def test_enum_comp_disabled(self):
        global Color

        class Color(Enum):
            RED = 1
            GREEN = 2

        def enum_comp(x: Color, y: Color) -> bool:
            return x == y

        with self.assertRaisesRegexWithHighlight(RuntimeError, "Unknown type name 'Color'", "Color"):
            torch.jit.script(enum_comp)
