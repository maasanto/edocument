# Copyright (c) 2025, Prilk Consulting BV and contributors
# For license information, please see license.txt

"""
Validator module for EDocument XML validation.
This module routes to profile-specific validators based on the EDocument Profile.

This module also provides common validation functions for XSD and Schematron
that can be used by all profiles.
"""

import re
from pathlib import Path
from typing import Optional

import frappe
from frappe import _

# EN16931 (CEN) Schematron messages embed the canonical rule code as a "[CODE]-"
# prefix, while PEPPOL and country rules carry it only in the failed-assert @id.
_CODE_PREFIX = re.compile(r"^\[([A-Za-z0-9.\-]+)\]\s*-?\s*")


def get_xml_validator(xml_bytes, edocument_profile):
	"""
	Get XML validator based on the profile.

	"""
	# Try to get validator from profile's validator_path if specified
	if edocument_profile.validator_path:
		try:
			validator_func = frappe.get_attr(edocument_profile.validator_path)
			return validator_func(xml_bytes, edocument_profile)
		except Exception as e:
			frappe.log_error(f"Error loading validator from path {edocument_profile.validator_path}: {e!s}")

	# Default: Use basic XML validator
	return validate_basic_xml(xml_bytes, edocument_profile)


def validate_basic_xml(xml_bytes, edocument_profile):
	"""
	Basic XML validator (placeholder implementation).

	"""
	# This is a placeholder implementation
	# You should implement actual XML validation based on your requirements
	# For example, you might want to:
	# 1. Use different validators for different profiles
	# 2. Validate XML structure and content
	# 3. Use common validation functions from this module

	try:
		# Basic XML structure validation
		from lxml import etree

		# Parse XML to check if it's well-formed
		parser = etree.XMLParser()
		etree.fromstring(xml_bytes, parser)

		# If validation passes
		return {"is_valid": True, "error": None}

	except etree.XMLSyntaxError as e:
		return {"is_valid": False, "error": f"XML syntax error: {e!s}"}
	except ImportError:
		# If lxml is not available, just check basic structure
		try:
			import xml.etree.ElementTree as ET

			ET.fromstring(xml_bytes)
			return {"is_valid": True, "error": None}
		except Exception as e:
			return {"is_valid": False, "error": f"XML validation error: {e!s}"}
	except Exception as e:
		return {"is_valid": False, "error": f"XML validation error: {e!s}"}


# ============================================================================
# Common XSD and Schematron Validation Functions
# These functions can be used by all profiles
# ============================================================================


def validate_xml_structure(xml_bytes: bytes) -> bytes:
	"""
	Validate XML structure (well-formedness).
	"""
	from lxml import etree

	try:
		parser = etree.XMLParser()
		root = etree.fromstring(xml_bytes, parser)
		# Return validated XML with pretty formatting
		return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")
	except etree.XMLSyntaxError as e:
		error_msg = f"XML structure validation failed: {e!s}"
		frappe.log_error(error_msg, "XML Validation")
		raise ValueError(error_msg)
	except Exception as e:
		error_msg = f"XML parsing failed: {e!s}"
		frappe.log_error(error_msg, "XML Validation")
		raise ValueError(error_msg)


def validate_xml_against_xsd_file(xml_bytes: bytes, xsd_file_path: Path | str) -> bytes:
	"""
	Validate XML against an XSD schema file.
	"""
	from lxml import etree

	xsd_path = Path(xsd_file_path) if isinstance(xsd_file_path, str) else xsd_file_path

	if not xsd_path.exists():
		error_msg = f"XSD schema file not found: {xsd_path}"
		frappe.log_error(error_msg, "XSD Validation")
		raise FileNotFoundError(error_msg)

	try:
		# Load and compile XSD schema
		schema_doc = etree.parse(str(xsd_path))
		xsd_schema = etree.XMLSchema(schema_doc)

		# Parse and validate XML
		parser = etree.XMLParser(schema=xsd_schema)
		xml_root = etree.fromstring(xml_bytes, parser)

		# Return validated XML with pretty formatting
		return etree.tostring(xml_root, pretty_print=True, xml_declaration=True, encoding="UTF-8")
	except etree.XMLSchemaError as e:
		error_msg = f"XSD validation failed: {e!s}"
		frappe.log_error(error_msg, "XSD Validation")
		raise ValueError(error_msg)
	except Exception as e:
		error_msg = f"XSD schema load or validation failed: {e!s}"
		frappe.log_error(error_msg, "XSD Validation")
		raise ValueError(error_msg)


def parse_svrl_report(report: str) -> list[dict]:
	"""
	Parse an SVRL (Schematron Validation Report Language) document into structured
	validation messages.

	Each returned dict carries:
		- "severity": "error" or "warning"
		- "code": the canonical rule code (e.g. "BR-CO-15", "PEPPOL-EN16931-R010")
			or None when no code can be determined
		- "message": the human-readable rule text, with any redundant "[CODE]-"
			prefix removed

	failed-assert elements are errors unless flagged as warnings; successful-report
	elements are surfaced as warnings (matching the previous behaviour).
	"""
	from lxml import objectify

	root = objectify.fromstring(report.encode("utf-8"))
	svrl_ns = {"svrl": "http://purl.oclc.org/dsdl/svrl"}

	messages = []

	def _add(node, severity):
		texts = node.xpath("svrl:text", namespaces=svrl_ns)
		raw = texts[0].text.strip() if texts and texts[0].text else ""
		if not raw:
			return

		# Prefer the canonical code embedded in the text ("[BR-52]-..."), since
		# some CEN rules expose only an auto-generated @id; fall back to @id.
		code = node.get("id")
		message = raw
		prefix_match = _CODE_PREFIX.match(raw)
		if prefix_match:
			code = prefix_match.group(1)
			message = raw[prefix_match.end() :].strip()

		messages.append({"severity": severity, "code": code, "message": message})

	for node in root.xpath("//svrl:failed-assert", namespaces=svrl_ns):
		severity = "warning" if node.get("flag") == "warning" else "error"
		_add(node, severity)

	for node in root.xpath("//svrl:successful-report", namespaces=svrl_ns):
		_add(node, "warning")

	return messages


def validate_xml_against_schematron_file(xml_bytes: bytes, xsl_file_path: Path | str) -> list[dict]:
	"""
	Validate XML against a single Schematron XSL stylesheet.

	Returns a list of structured validation messages (see parse_svrl_report).
	"""
	xsl_path = Path(xsl_file_path) if isinstance(xsl_file_path, str) else xsl_file_path

	if not xsl_path.exists():
		raise FileNotFoundError(f"XSL stylesheet not found: {xsl_path}")

	try:
		from saxonche import PySaxonProcessor
	except ImportError:
		raise ImportError("saxonche package is required for Schematron validation")

	xml_string = xml_bytes.decode("utf-8")

	# Run Schematron validation
	with PySaxonProcessor(license=False) as proc:
		xslt30_processor = proc.new_xslt30_processor()
		input_node = proc.parse_xml(xml_text=xml_string)
		executable = xslt30_processor.compile_stylesheet(stylesheet_file=str(xsl_path))
		report = executable.transform_to_string(xdm_node=input_node)

	return parse_svrl_report(report)


def validate_xml_against_schematron_files(xml_bytes: bytes, xsl_file_paths: list[Path | str]) -> list[dict]:
	"""
	Validate XML against multiple Schematron XSL stylesheets and combine results.

	Returns a flat list of structured validation messages (see parse_svrl_report).
	"""
	all_messages = []

	for xsl_file_path in xsl_file_paths:
		all_messages.extend(validate_xml_against_schematron_file(xml_bytes, xsl_file_path))

	return all_messages
