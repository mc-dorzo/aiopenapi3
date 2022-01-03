#!/usr/bin/env python

# CAVEAT UTILITOR
#
# This file was automatically generated by TatSu.
#
#    https://pypi.python.org/pypi/tatsu/
#
# Any changes you make to it will be overwritten the next time
# the file is generated.

from __future__ import annotations

from tatsu.objectmodel import Node
from tatsu.semantics import ModelBuilderSemantics


class ModelBase(Node):
    pass


class RuntimeExpressionModelBuilderSemantics(ModelBuilderSemantics):
    def __init__(self, context=None, types=None):
        types = [t for t in globals().values() if type(t) is type and issubclass(t, ModelBase)] + (types or [])
        super(RuntimeExpressionModelBuilderSemantics, self).__init__(context=context, types=types)


class RuntimeExpression(ModelBase):
    pass


class Expression(ModelBase):
    next = None
    root = None


class Header(ModelBase):
    key = None


class Query(ModelBase):
    key = None


class Path(ModelBase):
    key = None


class Body(ModelBase):
    fragment = None


class JSONPointer(ModelBase):
    tokens = None
