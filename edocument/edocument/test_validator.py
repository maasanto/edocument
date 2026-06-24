# Copyright (c) 2025, Prilk Consulting BV and Contributors
# See license.txt

import unittest

from edocument.edocument.validator import parse_svrl_report

# A minimal SVRL report exercising the cases the parser must handle:
# - a CEN rule whose canonical code is in the @id ("BR-CO-15")
# - a PEPPOL rule whose code is ONLY in the @id (no "[CODE]-" text prefix)
# - a warning (flag="warning")
# - a CEN rule with an auto-generated @id whose real code lives in the text prefix
# - a successful-report (surfaced as a warning)
SAMPLE_SVRL = """<?xml version="1.0" encoding="UTF-8"?>
<svrl:schematron-output xmlns:svrl="http://purl.oclc.org/dsdl/svrl">
	<svrl:failed-assert flag="fatal" id="BR-CO-15" location="/Invoice">
		<svrl:text>[BR-CO-15]-Invoice total amount with VAT (BT-112) = Invoice total amount without VAT (BT-109) + Invoice total VAT amount (BT-110).</svrl:text>
	</svrl:failed-assert>
	<svrl:failed-assert id="PEPPOL-EN16931-R010" location="/Invoice">
		<svrl:text>Buyer electronic address MUST be provided</svrl:text>
	</svrl:failed-assert>
	<svrl:failed-assert flag="warning" id="PEPPOL-EN16931-R002" location="/Invoice">
		<svrl:text>No more than one note is allowed on document level.</svrl:text>
	</svrl:failed-assert>
	<svrl:failed-assert flag="fatal" id="d12e32" location="/Invoice">
		<svrl:text>[BR-52]-Each Additional supporting document (BG-24) shall contain a Supporting document reference (BT-122).</svrl:text>
	</svrl:failed-assert>
	<svrl:successful-report id="PEPPOL-EN16931-R040" location="/Invoice">
		<svrl:text>Reported as informational.</svrl:text>
	</svrl:successful-report>
</svrl:schematron-output>"""


class TestParseSvrlReport(unittest.TestCase):
	def setUp(self):
		self.messages = parse_svrl_report(SAMPLE_SVRL)
		self.by_code = {m["code"]: m for m in self.messages}

	def test_all_assertions_parsed(self):
		self.assertEqual(len(self.messages), 5)

	def test_code_from_id_attribute(self):
		# PEPPOL rules carry the code only in @id.
		self.assertIn("PEPPOL-EN16931-R010", self.by_code)
		self.assertEqual(self.by_code["PEPPOL-EN16931-R010"]["severity"], "error")

	def test_code_from_text_prefix_overrides_generated_id(self):
		# CEN rule with an auto-generated @id: the canonical code is in "[BR-52]-".
		self.assertIn("BR-52", self.by_code)
		self.assertNotIn("d12e32", self.by_code)
		# The redundant "[BR-52]-" prefix is stripped from the displayed message.
		self.assertFalse(self.by_code["BR-52"]["message"].startswith("["))
		self.assertTrue(self.by_code["BR-52"]["message"].startswith("Each Additional"))

	def test_redundant_prefix_stripped_for_cen_rule(self):
		message = self.by_code["BR-CO-15"]["message"]
		self.assertFalse(message.startswith("["))
		self.assertTrue(message.startswith("Invoice total amount with VAT"))

	def test_warning_flag_is_respected(self):
		self.assertEqual(self.by_code["PEPPOL-EN16931-R002"]["severity"], "warning")

	def test_successful_report_is_a_warning(self):
		self.assertEqual(self.by_code["PEPPOL-EN16931-R040"]["severity"], "warning")

	def test_empty_report_returns_empty_list(self):
		empty = '<svrl:schematron-output xmlns:svrl="http://purl.oclc.org/dsdl/svrl"/>'
		self.assertEqual(parse_svrl_report(empty), [])
