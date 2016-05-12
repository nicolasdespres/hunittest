# -*- encoding: utf-8 -*-
"""Routines to handle filtering rules.
"""


from enum import Enum
from collections import namedtuple
import functools
import re
import argparse
import fnmatch


class RuleOperator(Enum):
    include = "+"
    exclude = "-"

class Rule(namedtuple("BaseRule", ("operator", "pattern"))):

    def __new__(cls, operator=None, pattern=None):
        if not isinstance(operator, RuleOperator):
            raise TypeError("must be a rule operator, not {}"
                            .format(type(operator).__name__))
        if not pattern:
            raise ValueError("pattern cannot be empty")
        try:
            re.compile(pattern)
        except re.error:
            raise ValueError("invalid pattern '{}': {}"
                             .format(pattern, str(e)))
        return super(Rule, cls).__new__(cls, operator, pattern)

    @property
    def include(self):
        return self.operator is RuleOperator.include

    @property
    def exclude(self):
        return self.operator is RuleOperator.exclude

    def __str__(self):
        return "{} /{}/".format(self.operator.value, self.pattern)

    def match(self, string):
        # FIXME(Nicolas Despres): Remove this test. It is here only
        #  because when used from hunittest.cli.reported_collect() we
        #  may encounter other kind of object.
        if not isinstance(string, str):
            return True
        # print("STRING", repr(string))
        if re.search(self.pattern, string):
            if self.include:
                r = True
            elif self.exclude:
                r = False
            else:
                raise RuntimeError("unsupported rule operator: {}"
                                   .format(self.operator))
        else:
            if self.include:
                r = False
            elif self.exclude:
                r = True
            else:
                raise RuntimeError("unsupported rule operator: {}"
                                   .format(self.operator))
        # print("apply rule {} on {} => {}".format(self, string, r))
        return r

    def __repr__(self):
        return "{}({}, {!r})"\
            .format(type(self).__name__,
                    str(self.operator),
                    self.pattern)

class FilterRules(object):

    def __init__(self, rules=None):
        self._rules = []
        self.include_everything()
        self.exclude_nothing()
        if rules is None:
            rules = []
        for rule in rules:
            self.append(rule)

    def append(self, rule):
        self._rules.append(rule)

    def include_pattern(self, pattern):
        self.append(Rule(RuleOperator.include, pattern))

    def include_prefix(self, prefix):
        self.include_pattern(r"^{}".format(prefix))

    def include_everything(self):
        self.include_pattern(r"^.*$")

    def exclude_pattern(self, pattern):
        self.append(Rule(RuleOperator.exclude, pattern))

    def exclude_prefix(self, prefix):
        self.exclude_pattern(r"^{}".format(prefix))

    def exclude_nothing(self):
        self.exclude_pattern(r"nothing^")

    def __iter__(self):
        return iter(self._rules)

    def __call__(self, iterable, key=None):
        # print("FILTERRULE ON", repr(iterable))
        def matcher(rule, item):
            # print("ITEM", repr(item))
            if key is None:
                string = item
            else:
                string = key(item)
            # print("TESTED STRING", string)
            return rule.match(string)
        for rule in self._rules:
            iterable = filter(functools.partial(matcher, rule), iterable)
        return iterable

    def __repr__(self):
        return "{:s}([{}])".format(type(self).__name__,
                                   ", ".join("'{!s}'".format(r)
                                             for r in self._rules))

class PatternType(Enum):
    glob = 1
    regex = 2

def pattern_from_string(pattern_type, string):
    if pattern_type is PatternType.glob:
        return fnmatch.translate(string)
    elif pattern_type is PatternType.regex:
        return string
    else:
        raise ValueError("unsupported pattern type: {}".format(pattern_type))

class FilterAction(argparse.Action):
    """A filter action for argparse."""

    DEST = "filter_rules"

    def __init__(self, option_strings, dest, nargs=None,
                 filter_rule_operator=None, pattern_type=None,
                 **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        if filter_rule_operator is None:
            raise ValueError("filter_rule_operator must be set")
        if not isinstance(filter_rule_operator, RuleOperator):
            raise TypeError("must be a rule operator, not {!r}"
                            .format(type(rule_operator).__name__))
        self.rule_operator = filter_rule_operator
        if pattern_type is None:
            raise ValueError("pattern_type must be set")
        if not isinstance(pattern_type, PatternType):
            raise TypeError("must be a pattern type, not {!r}"
                            .format(type(pattern_type).__name__))
        self.pattern_type = pattern_type
        super(FilterAction, self).__init__(option_strings,
                                           self.DEST,
                                           **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        filter_rules = getattr(namespace, self.DEST)
        if filter_rules is None:
            filter_rules = FilterRules()
            setattr(namespace, self.DEST, filter_rules)
        pattern = pattern_from_string(self.pattern_type, values)
        filter_rules.append(Rule(self.rule_operator, pattern))
