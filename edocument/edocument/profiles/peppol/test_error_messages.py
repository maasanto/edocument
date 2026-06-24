# Copyright (c) 2025, Prilk Consulting BV and Contributors
# See license.txt

try:
	from frappe.tests import IntegrationTestCase as TestCase
except ImportError:
	from frappe.tests.utils import FrappeTestCase as TestCase

from edocument.edocument.profiles.peppol.error_messages import (
	build_validation_report,
	get_friendly_message,
)


class TestErrorMessages(TestCase):
	def test_known_code_has_friendly_message(self):
		friendly = get_friendly_message("BR-CO-15")
		self.assertTrue(friendly)
		# The friendly text is a real explanation, not the bare code.
		self.assertNotEqual(friendly, "BR-CO-15")

	def test_unknown_code_returns_none(self):
		# Obscure UBL conformance rules are intentionally not mapped.
		self.assertIsNone(get_friendly_message("UBL-CR-001"))

	def test_blank_code_returns_none(self):
		self.assertIsNone(get_friendly_message(None))
		self.assertIsNone(get_friendly_message(""))

	def test_empty_messages_render_nothing(self):
		self.assertEqual(build_validation_report([]), "")

	def test_report_shows_friendly_text_and_collapsed_technical(self):
		messages = [
			{
				"severity": "error",
				"code": "PEPPOL-EN16931-R010",
				"message": "Buyer electronic address MUST be provided",
			}
		]
		html = build_validation_report(messages)

		# Friendly explanation up front...
		self.assertIn(get_friendly_message("PEPPOL-EN16931-R010"), html)
		# ...with the raw code + technical text in a collapsed section.
		self.assertIn("<details", html)
		self.assertIn("[PEPPOL-EN16931-R010]", html)
		self.assertIn("Buyer electronic address MUST be provided", html)

	def test_unmapped_code_falls_back_to_technical_text(self):
		messages = [{"severity": "error", "code": "UBL-CR-001", "message": "Some raw rule text."}]
		html = build_validation_report(messages)
		# Nothing is hidden: the raw text is shown as the headline.
		self.assertIn("Some raw rule text.", html)

	def test_report_escapes_html_exactly_once(self):
		messages = [{"severity": "warning", "code": None, "message": "value <b>x</b> & y"}]
		html = build_validation_report(messages)
		# Raw markup must be escaped...
		self.assertNotIn("<b>x</b>", html)
		self.assertIn("&lt;b&gt;x&lt;/b&gt;", html)
		# ...but not double-escaped (the raw technical text must stay faithful).
		self.assertNotIn("&amp;lt;", html)
		self.assertNotIn("&amp;amp;", html)
