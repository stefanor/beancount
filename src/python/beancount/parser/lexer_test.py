"""
Tests for lexer.
"""
import datetime
import functools
import textwrap
import unittest
import re

from beancount.core.amount import D
from beancount.parser import lexer


def print_tokens(tokens):
    """A function for printing a list of tokens, for testing.

    Args:
      tokens: A list of token tuples.
    """
    print()
    print(',--------------------------------')
    for token in tokens:
        print('{},'.format(token))
    print('`--------------------------------')


class TestLexer(unittest.TestCase):
    """Test output of the lexer."""

    def lex_tokens(fun):
        @functools.wraps(fun)
        def wrapped(self):
            string = fun.__doc__
            builder = lexer.LexBuilder()
            # Set default value for test_overlong_string().
            builder.long_string_maxlines_default = 8
            tokens = list(lexer.lex_iter_string(textwrap.dedent(string),
                                                builder))
            return fun(self, tokens, builder.errors)
        wrapped.__doc__ = None
        return wrapped

    @lex_tokens
    def test_lex_iter(self, tokens, errors):
        """\
          2013-05-18 2014-01-02 2014/01/02
          Assets:US:Bank:Checking
          Liabilities:US:Bank:Credit
          Other:Bank
          USD GOOG TEST_D TEST_3 TEST-D TEST-3 NT
          "Nice dinner at Mermaid Inn"
          ""
          123 123.45 123.456789 -123 -123.456789
          #sometag123
          ^sometag123
        """
        self.assertEqual([
            ('DATE', 1, '2013-05-18', datetime.date(2013, 5, 18)),
            ('DATE', 1, '2014-01-02', datetime.date(2014, 1, 2)),
            ('DATE', 1, '2014/01/02', datetime.date(2014, 1, 2)),
            ('EOL', 2, '\n', None),
            ('ACCOUNT', 2, 'Assets:US:Bank:Checking', 'Assets:US:Bank:Checking'),
            ('EOL', 3, '\n', None),
            ('ACCOUNT', 3, 'Liabilities:US:Bank:Credit', 'Liabilities:US:Bank:Credit'),
            ('EOL', 4, '\n', None),
            ('ACCOUNT', 4, 'Other:Bank', 'Other:Bank'),
            ('EOL', 5, '\n', None),
            ('CURRENCY', 5, 'USD', 'USD'),
            ('CURRENCY', 5, 'GOOG', 'GOOG'),
            ('CURRENCY', 5, 'TEST_D', 'TEST_D'),
            ('CURRENCY', 5, 'TEST_3', 'TEST_3'),
            ('CURRENCY', 5, 'TEST-D', 'TEST-D'),
            ('CURRENCY', 5, 'TEST-3', 'TEST-3'),
            ('CURRENCY', 5, 'NT', 'NT'),
            ('EOL', 6, '\n', None),
            ('STRING', 6, '"Nice dinner at Mermaid Inn"', 'Nice dinner at Mermaid Inn'),
            ('EOL', 7, '\n', None),
            ('STRING', 7, '""', ''),
            ('EOL', 8, '\n', None),
            ('NUMBER', 8, '123', D('123')),
            ('NUMBER', 8, '123.45', D('123.45')),
            ('NUMBER', 8, '123.456789', D('123.456789')),
            ('NUMBER', 8, '-123', D('-123')),
            ('NUMBER', 8, '-123.456789', D('-123.456789')),
            ('EOL', 9, '\n', None),
            ('TAG', 9, '#sometag123', 'sometag123'),
            ('EOL', 10, '\n', None),
            ('LINK', 10, '^sometag123', 'sometag123'),
            ('EOL', 11, '\n', None),
            ], tokens)

    @lex_tokens
    def test_lex_indent(self, tokens, errors):
        """\
          2014-07-05 *
            Equity:Something
        """
        self.assertEqual([
            ('DATE', 1, '2014-07-05', datetime.date(2014, 7, 5)),
            ('FLAG', 1, '*', None),
            ('EOL', 2, '\n', None),
            ('INDENT', 2, '  ', None),
            ('ACCOUNT', 2, 'Equity:Something', 'Equity:Something'),
            ('EOL', 3, '\n', None),
            ], tokens)

    @lex_tokens
    def test_comma_currencies(self, tokens, errors):
        """\
          USD,CAD,AUD
        """
        self.assertEqual([
            ('CURRENCY', 1, 'USD', 'USD'),
            ('COMMA', 1, ',', None),
            ('CURRENCY', 1, 'CAD', 'CAD'),
            ('COMMA', 1, ',', None),
            ('CURRENCY', 1, 'AUD', 'AUD'),
            ('EOL', 2, '\n', None),
            ], tokens)

    @lex_tokens
    def test_number_okay(self, tokens, errors):
        """\
          1001 USD
          1002.00 USD
          -1001 USD
          -1002.00 USD
          +1001 USD
          +1002.00 USD
          1,001 USD
          1,002.00 USD
          -1,001 USD
          -1,002.00 USD
          +1,001 USD
          +1,002.00 USD
        """
        self.assertFalse(errors)

    @lex_tokens
    def test_number_space(self, tokens, errors):
        """\
          - 1002.00 USD
        """
        self.assertTrue(errors)

    @lex_tokens
    def test_number_dots(self, tokens, errors):
        """\
          1.234.00 USD
        """
        self.assertTrue(errors)

    @lex_tokens
    def test_number_no_integer(self, tokens, errors):
        """\
          .2347 USD
        """
        # Note: this is not supported in order to make the lexer regexp more tractable.
        # If we write our own lexer eventually we should be able to accept these.
        self.assertTrue(errors)

    @lex_tokens
    def test_currency_number(self, tokens, errors):
        """\
          555.00 CAD.11
        """
        self.assertEqual([
            ('NUMBER', 1, '555.00', D('555.00')),
            ('CURRENCY', 1, 'CAD.11', 'CAD.11'),
            ('EOL', 2, '\n', None),
            ], tokens)

    @lex_tokens
    def test_currency_dash(self, tokens, errors):
        """\
          TEST-DA
        """
        self.assertEqual([
            ('CURRENCY', 1, 'TEST-DA', 'TEST-DA'),
            ('EOL', 2, '\n', None),
            ], tokens)
        self.assertEqual(0, len(errors))

    @lex_tokens
    def test_bad_date(self, tokens, errors):
        """\
          2013-12-98
        """
        self.assertEqual([
            ('ERROR', 1, '2013-12-98', None),
            ('EOL', 2, '\n', None),
        ], tokens)
        self.assertTrue(errors)
        self.assertTrue(re.search('out of range', errors[0].message) or
                        re.search('month must be', errors[0].message))

    @lex_tokens
    def test_date_followed_by_number(self, tokens, errors):
        """\
          2013-12-228
        """
        self.assertEqual([
            ('ERROR', 1, '2013-12-228', None),
            ('EOL', 2, '\n', None),
            ], tokens)

    @lex_tokens
    def test_single_letter_account(self, tokens, errors):
        """\
          Assets:A
        """
        self.assertEqual([
            ('ERROR', 1, 'A', None),
            ('EOL', 2, '\n', None),
        ], tokens)
        self.assertTrue(errors)
        self.assertTrue(re.search('erroneous token', errors[0].message))

    @lex_tokens
    def test_invalid_directive(self, tokens, errors):
        """\
          2008-03-01 check Assets:BestBank:Savings 2340.19 USD
        """
        self.assertEqual([
            ('DATE', 1, '2008-03-01', datetime.date(2008, 3, 1)),
            ('ERROR', 1, 'c', None),
            ('ACCOUNT', 1, 'Assets:BestBank:Savings', 'Assets:BestBank:Savings'),
            ('NUMBER', 1, '2340.19', D('2340.19')),
            ('CURRENCY', 1, 'USD', 'USD'),
            ('EOL', 2, '\n', None),
            ], tokens)
        self.assertTrue(errors)
        self.assertTrue(re.search(r'\bcheck\b', errors[0].message))

    @lex_tokens
    def test_invalid_directive(self, tokens, errors):
        """\
          2008-03-01 check Assets:BestBank:Savings 2340.19 USD
        """
        self.assertEqual([
            ('DATE', 1, '2008-03-01', datetime.date(2008, 3, 1)),
            ('ERROR', 1, 'c', None),
            ('ACCOUNT', 1, 'Assets:BestBank:Savings', 'Assets:BestBank:Savings'),
            ('NUMBER', 1, '2340.19', D('2340.19')),
            ('CURRENCY', 1, 'USD', 'USD'),
            ('EOL', 2, '\n', None),
            ], tokens)
        self.assertTrue(errors)
        self.assertTrue(re.search(r'\bcheck\b', errors[0].message))

    @lex_tokens
    def test_overlong_string(self, tokens, errors):
        """
          2014-01-01 note Assets:Temporary "Bla bla" "

          2014-02-01 open Liabilities:US:BankWithLongName:Credit-Card:Account01
          2014-02-02 open Liabilities:US:BankWithLongName:Credit-Card:Account02
          2014-02-03 open Liabilities:US:BankWithLongName:Credit-Card:Account03
          2014-02-04 open Liabilities:US:BankWithLongName:Credit-Card:Account04
          2014-02-05 open Liabilities:US:BankWithLongName:Credit-Card:Account05
          2014-02-06 open Liabilities:US:BankWithLongName:Credit-Card:Account06
          2014-02-07 open Liabilities:US:BankWithLongName:Credit-Card:Account07
          2014-02-08 open Liabilities:US:BankWithLongName:Credit-Card:Account08
          2014-02-09 open Liabilities:US:BankWithLongName:Credit-Card:Account09
          2014-02-10 open Liabilities:US:BankWithLongName:Credit-Card:Account10

          2014-02-02 note Assets:Temporary "Bla bla"
        """
        self.assertTrue(errors)
        self.assertTrue(re.search(r'Overly long', errors[0].message))
