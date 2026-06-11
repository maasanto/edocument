# Copyright (c) 2025, Prilk Consulting BV and Contributors
# See license.txt

import frappe
from frappe.utils.data import flt
from lxml import etree as ET

try:
	from frappe.tests import IntegrationTestCase as TestCase
except ImportError:
	from frappe.tests.utils import FrappeTestCase as TestCase

from edocument.edocument.profiles.peppol import UBL_NAMESPACES
from edocument.edocument.profiles.peppol.generator import PEPPOLGenerator

CBC = UBL_NAMESPACES["cbc"]


def _build_legal_monetary_total(invoice, document_type="Invoice"):
	"""Run PEPPOLGenerator._set_totals against a stand-in invoice and return the
	LegalMonetaryTotal element. __init__ is bypassed because it loads related
	addresses/contacts from the database, which _set_totals does not need."""
	generator = PEPPOLGenerator.__new__(PEPPOLGenerator)
	generator.invoice = invoice
	generator.document_type = document_type
	generator.root = ET.Element("Root")
	generator._set_totals()
	return generator.root.find(f"{{{UBL_NAMESPACES['cac']}}}LegalMonetaryTotal")


def _amount(legal_total, tag):
	element = legal_total.find(f"{{{CBC}}}{tag}")
	return flt(element.text, 2) if element is not None else None


class TestBRCO16Totals(TestCase):
	"""LegalMonetaryTotal must satisfy EN16931 rule BR-CO-16:
	PayableAmount = TaxInclusiveAmount - PrepaidAmount + PayableRoundingAmount.

	Regression for rounded invoices: outstanding_amount tracks rounded_total, which can
	differ from grand_total rounded to 2 decimals. Without emitting PayableRoundingAmount
	(BT-114) to absorb that gap, the schematron rejected the invoice. The gap appears not
	only with a configured Round Off but also from a sub-cent divergence between the two
	roundings (e.g. grand_total 2047.925 -> 2047.92 while rounded_total is 2047.93)."""

	def _assert_br_co_16(self, legal_total):
		payable = _amount(legal_total, "PayableAmount")
		tax_inclusive = _amount(legal_total, "TaxInclusiveAmount")
		prepaid = _amount(legal_total, "PrepaidAmount") or 0.0
		rounding = _amount(legal_total, "PayableRoundingAmount") or 0.0
		self.assertEqual(payable, flt(tax_inclusive - prepaid + rounding, 2))

	def _invoice(self, *, grand_total, rounded_total, outstanding_amount):
		return frappe._dict(
			total=grand_total,
			net_total=grand_total,
			grand_total=grand_total,
			rounded_total=rounded_total,
			currency="EUR",
			taxes=[],
			outstanding_amount=outstanding_amount,
		)

	def test_subcent_rounding_divergence(self):
		# The real regression: grand_total 2047.925 displays as 2047.92 but the customer owes
		# the rounded 2047.93. rounding_adjustment (0.005) would round to 0, so BT-114 must be
		# derived as the residual, not read from the stored adjustment.
		legal_total = _build_legal_monetary_total(
			self._invoice(grand_total=2047.925, rounded_total=2047.93, outstanding_amount=2047.93)
		)
		self.assertEqual(_amount(legal_total, "TaxInclusiveAmount"), 2047.92)
		self.assertEqual(_amount(legal_total, "PayableRoundingAmount"), 0.01)
		self.assertIsNone(legal_total.find(f"{{{CBC}}}PrepaidAmount"))
		self._assert_br_co_16(legal_total)

	def test_rounded_up_unpaid_invoice(self):
		# grand_total rounds up to the next whole unit; outstanding tracks the rounded total
		legal_total = _build_legal_monetary_total(
			self._invoice(grand_total=99.99, rounded_total=100.00, outstanding_amount=100.00)
		)
		self.assertEqual(_amount(legal_total, "PayableRoundingAmount"), 0.01)
		self.assertIsNone(legal_total.find(f"{{{CBC}}}PrepaidAmount"))
		self._assert_br_co_16(legal_total)

	def test_rounded_down_unpaid_invoice(self):
		# grand_total rounds down; the rounding residual is negative
		legal_total = _build_legal_monetary_total(
			self._invoice(grand_total=100.01, rounded_total=100.00, outstanding_amount=100.00)
		)
		self.assertEqual(_amount(legal_total, "PayableRoundingAmount"), -0.01)
		self._assert_br_co_16(legal_total)

	def test_rounded_partially_paid_invoice(self):
		# Paid portion measured against the rounded total; rounding still reconciles the remainder
		legal_total = _build_legal_monetary_total(
			self._invoice(grand_total=99.99, rounded_total=100.00, outstanding_amount=40.00)
		)
		self.assertEqual(_amount(legal_total, "PrepaidAmount"), 60.00)
		self.assertEqual(_amount(legal_total, "PayableRoundingAmount"), 0.01)
		self._assert_br_co_16(legal_total)

	def test_no_rounding_omits_rounding_amount(self):
		# Behaviour is unchanged when grand_total and rounded_total agree
		legal_total = _build_legal_monetary_total(
			self._invoice(grand_total=100.00, rounded_total=100.00, outstanding_amount=100.00)
		)
		self.assertIsNone(legal_total.find(f"{{{CBC}}}PayableRoundingAmount"))
		self.assertIsNone(legal_total.find(f"{{{CBC}}}PrepaidAmount"))
		self._assert_br_co_16(legal_total)

	def test_fully_paid_no_rounding(self):
		# Fully paid invoice: prepaid covers the total, no rounding residual
		legal_total = _build_legal_monetary_total(
			self._invoice(grand_total=100.00, rounded_total=100.00, outstanding_amount=0.0)
		)
		self.assertEqual(_amount(legal_total, "PrepaidAmount"), 100.00)
		self.assertIsNone(legal_total.find(f"{{{CBC}}}PayableRoundingAmount"))
		self._assert_br_co_16(legal_total)

	def test_disabled_rounded_total_falls_back_to_grand_total(self):
		# When rounded_total is disabled it is stored as 0; the total due falls back to grand_total
		legal_total = _build_legal_monetary_total(
			self._invoice(grand_total=100.00, rounded_total=0.0, outstanding_amount=100.00)
		)
		self.assertIsNone(legal_total.find(f"{{{CBC}}}PayableRoundingAmount"))
		self.assertIsNone(legal_total.find(f"{{{CBC}}}PrepaidAmount"))
		self._assert_br_co_16(legal_total)

	def test_credit_note_skips_prepaid_and_rounding(self):
		# Credit notes use grand_total directly for PayableAmount and emit neither BT-113 nor BT-114
		legal_total = _build_legal_monetary_total(
			self._invoice(grand_total=99.99, rounded_total=100.00, outstanding_amount=100.00),
			document_type="CreditNote",
		)
		self.assertIsNone(legal_total.find(f"{{{CBC}}}PrepaidAmount"))
		self.assertIsNone(legal_total.find(f"{{{CBC}}}PayableRoundingAmount"))

	def test_rounding_amount_precedes_payable_amount(self):
		# UBL XSD requires PrepaidAmount, then PayableRoundingAmount, then PayableAmount
		legal_total = _build_legal_monetary_total(
			self._invoice(grand_total=99.99, rounded_total=100.00, outstanding_amount=40.00)
		)
		tags = [ET.QName(child).localname for child in legal_total]
		self.assertLess(tags.index("PrepaidAmount"), tags.index("PayableRoundingAmount"))
		self.assertLess(tags.index("PayableRoundingAmount"), tags.index("PayableAmount"))
