# Copyright (c) 2025, Prilk Consulting BV and contributors
# For license information, please see license.txt

"""
Human-friendly explanations for PEPPOL / EN16931 validation rule codes.

Schematron rule codes (BR-CO-15, PEPPOL-EN16931-R010, ...) are precise but
opaque to end users. This module maps the codes that realistically occur for
ERPNext/Dokos-generated invoices to short, plain-language explanations, and
renders a validation report that shows the friendly text up front with the raw
technical messages tucked into a collapsed section.

Codes without a friendly mapping fall back to their raw technical text, so no
information is ever hidden.
"""

import frappe
from frappe import _
from frappe.utils import escape_html

# Friendly explanations keyed by rule code. Values are English source strings
# (the gettext msgids) and are translated at lookup time via get_friendly_message
# so the report follows the viewing user's language rather than the language that
# happened to be active when this module was first imported.
PEPPOL_RULE_MESSAGES = {
	# --- Mandatory document fields ---
	"BR-01": "The invoice is missing its specification identifier (the PEPPOL/EN16931 profile marker).",
	"BR-02": "The invoice number is missing.",
	"BR-03": "The invoice issue date is missing.",
	"BR-04": "The invoice type code is missing.",
	"BR-05": "The invoice currency is missing.",
	"BR-06": "The seller (your company) name is missing.",
	"BR-07": "The buyer (customer) name is missing.",
	"BR-08": "The seller postal address is missing.",
	"BR-09": "The seller address is missing a country.",
	"BR-10": "The buyer postal address is missing.",
	"BR-11": "The buyer address is missing a country.",
	"BR-12": "The sum of line net amounts is missing from the invoice totals.",
	"BR-13": "The invoice total without VAT is missing.",
	"BR-14": "The invoice total with VAT is missing.",
	"BR-15": "The amount due for payment is missing.",
	"BR-16": "The invoice has no lines. Add at least one item.",
	"BR-17": "A payee name is required when the payee differs from the seller.",
	"BR-18": "A seller tax representative name is required when a tax representative is declared.",
	"BR-19": "A seller tax representative address is required when a tax representative is declared.",
	"BR-20": "A seller tax representative country is required when a tax representative is declared.",
	"BR-21": "An invoice line is missing its line number.",
	"BR-22": "An invoice line is missing its quantity.",
	"BR-23": "An invoice line is missing its unit of measure.",
	"BR-24": "An invoice line is missing its net amount.",
	"BR-25": "An invoice line is missing the item name.",
	"BR-26": "An invoice line is missing the item unit price.",
	"BR-27": "An item net price cannot be negative.",
	"BR-28": "An item gross price cannot be negative.",
	"BR-29": "The invoicing period end date must be on or after its start date.",
	"BR-30": "An invoice line period end date must be on or after its start date.",
	"BR-31": "A document-level discount is missing its amount.",
	"BR-32": "A document-level discount is missing its VAT category.",
	"BR-33": "A document-level discount needs a reason or a reason code.",
	"BR-36": "A document-level charge is missing its amount.",
	"BR-37": "A document-level charge is missing its VAT category.",
	"BR-38": "A document-level charge needs a reason or a reason code.",
	"BR-41": "An invoice line discount is missing its amount.",
	"BR-42": "An invoice line discount needs a reason or a reason code.",
	"BR-43": "An invoice line charge is missing its amount.",
	"BR-44": "An invoice line charge needs a reason or a reason code.",
	"BR-52": "An attached supporting document is missing its reference.",
	"BR-53": "When an accounting currency is set, the VAT total in that currency is required.",
	"BR-54": "Each item attribute needs both a name and a value.",
	"BR-55": "A reference to a preceding invoice is missing its number.",
	"BR-57": "A 'deliver to' address is missing its country.",
	"BR-61": "For a credit transfer payment, the payment account (IBAN) is required.",
	"BR-62": "The seller electronic address needs a scheme identifier (e.g. its EAS code).",
	"BR-63": "The buyer electronic address needs a scheme identifier (e.g. its EAS code).",
	"BR-64": "The item standard identifier needs a scheme identifier.",
	"BR-65": "The item classification identifier needs a scheme identifier.",
	# --- Calculation and consistency rules ---
	"BR-CO-03": "Provide either the VAT point date or the VAT point date code, not both.",
	"BR-CO-04": "Every invoice line must have a VAT category.",
	"BR-CO-05": "A document-level discount reason and reason code must describe the same discount.",
	"BR-CO-06": "A document-level charge reason and reason code must describe the same charge.",
	"BR-CO-09": "VAT identifiers must start with a 2-letter country code (e.g. FR, BE).",
	"BR-CO-10": "The sum of line net amounts does not match the individual line amounts.",
	"BR-CO-11": "The total of document-level discounts does not match the individual discounts.",
	"BR-CO-12": "The total of document-level charges does not match the individual charges.",
	"BR-CO-13": "The total without VAT does not equal lines minus discounts plus charges.",
	"BR-CO-14": "The total VAT amount does not equal the sum of the VAT breakdown amounts.",
	"BR-CO-15": "The total with VAT must equal the total without VAT plus the total VAT amount. Check the line amounts, taxes and rounding.",
	"BR-CO-16": "The amount due does not equal the total with VAT minus the amount paid plus rounding.",
	"BR-CO-17": "A VAT breakdown amount does not equal its taxable amount times the VAT rate (rounded to 2 decimals).",
	"BR-CO-18": "The invoice needs at least one VAT breakdown.",
	"BR-CO-19": "When an invoicing period is used, fill in its start and/or end date.",
	"BR-CO-20": "When an invoice line period is used, fill in its start and/or end date.",
	"BR-CO-21": "A document-level discount needs a reason or a reason code.",
	"BR-CO-25": "When an amount is due, provide a payment due date or payment terms.",
	"BR-CO-26": "Provide a seller identifier, legal registration number or VAT number so the buyer can identify you.",
	# --- Decimal precision rules ---
	"BR-DEC-01": "A document-level discount amount can have at most 2 decimal places.",
	"BR-DEC-02": "A document-level discount base amount can have at most 2 decimal places.",
	"BR-DEC-05": "A document-level charge amount can have at most 2 decimal places.",
	"BR-DEC-09": "The sum of line net amounts can have at most 2 decimal places.",
	"BR-DEC-12": "The invoice total without VAT can have at most 2 decimal places.",
	"BR-DEC-13": "The invoice total VAT amount can have at most 2 decimal places.",
	"BR-DEC-14": "The invoice total with VAT can have at most 2 decimal places.",
	"BR-DEC-15": "The VAT total in accounting currency can have at most 2 decimal places.",
	"BR-DEC-16": "The paid amount can have at most 2 decimal places.",
	"BR-DEC-17": "The rounding amount can have at most 2 decimal places.",
	"BR-DEC-18": "The amount due for payment can have at most 2 decimal places.",
	"BR-DEC-19": "A VAT category taxable amount can have at most 2 decimal places.",
	# --- VAT category: Standard rated ---
	"BR-S-01": "Standard-rated lines require a matching 'Standard rated' VAT breakdown.",
	"BR-S-02": "Standard-rated lines require the seller's VAT or tax registration number.",
	"BR-S-05": "Standard-rated lines must have a VAT rate greater than zero.",
	"BR-S-08": "The standard-rated taxable amount does not match the sum of its lines, charges and discounts.",
	"BR-S-09": "The standard-rated VAT amount does not equal the taxable amount times the rate.",
	"BR-S-10": "A standard-rated VAT breakdown must not carry a VAT exemption reason.",
	# --- VAT category: Exempt from VAT ---
	"BR-E-01": "Exempt lines require exactly one 'Exempt from VAT' breakdown.",
	"BR-E-02": "Exempt lines require the seller's VAT or tax registration number.",
	"BR-E-05": "Exempt lines must have a 0% VAT rate.",
	"BR-E-08": "The exempt taxable amount does not match the sum of its lines, charges and discounts.",
	"BR-E-09": "The exempt VAT amount must be zero.",
	"BR-E-10": "An exempt VAT breakdown must state an exemption reason or reason code.",
	# --- VAT category: Zero rated ---
	"BR-Z-01": "Zero-rated lines require exactly one 'Zero rated' breakdown.",
	"BR-Z-02": "Zero-rated lines require the seller's VAT or tax registration number.",
	"BR-Z-05": "Zero-rated lines must have a 0% VAT rate.",
	"BR-Z-08": "The zero-rated taxable amount does not match the sum of its lines, charges and discounts.",
	"BR-Z-09": "The zero-rated VAT amount must be zero.",
	"BR-Z-10": "A zero-rated VAT breakdown must not carry a VAT exemption reason.",
	# --- VAT category: Reverse charge ---
	"BR-AE-01": "Reverse-charge lines require exactly one 'VAT reverse charge' breakdown.",
	"BR-AE-02": "Reverse charge requires both the seller's and the buyer's VAT (or registration) identifiers.",
	"BR-AE-05": "Reverse-charge lines must have a 0% VAT rate.",
	"BR-AE-08": "The reverse-charge taxable amount does not match the sum of its lines, charges and discounts.",
	"BR-AE-09": "The reverse-charge VAT amount must be zero.",
	"BR-AE-10": "A reverse-charge VAT breakdown must state a 'Reverse charge' exemption reason.",
	# --- VAT category: Export outside the EU ---
	"BR-G-01": "'Export outside the EU' lines require exactly one matching VAT breakdown.",
	"BR-G-02": "Export lines require the seller's VAT or tax representative VAT number.",
	"BR-G-05": "Export lines must have a 0% VAT rate.",
	"BR-G-08": "The export taxable amount does not match the sum of its lines, charges and discounts.",
	"BR-G-09": "The export VAT amount must be zero.",
	"BR-G-10": "An export VAT breakdown must state an 'Export outside the EU' exemption reason.",
	# --- VAT category: Intra-community supply ---
	"BR-IC-01": "Intra-community supply lines require exactly one matching VAT breakdown.",
	"BR-IC-02": "Intra-community supply requires both the seller's VAT number and the buyer's VAT number.",
	"BR-IC-05": "Intra-community supply lines must have a 0% VAT rate.",
	"BR-IC-08": "The intra-community taxable amount does not match the sum of its lines, charges and discounts.",
	"BR-IC-09": "The intra-community VAT amount must be zero.",
	"BR-IC-10": "An intra-community VAT breakdown must state an 'Intra-community supply' exemption reason.",
	"BR-IC-11": "Intra-community supply requires a delivery date or an invoicing period.",
	"BR-IC-12": "Intra-community supply requires a 'deliver to' country code.",
	# --- VAT category: Not subject to VAT ---
	"BR-O-01": "'Not subject to VAT' lines require exactly one matching VAT breakdown.",
	"BR-O-02": "A 'Not subject to VAT' invoice must not carry any VAT identifiers.",
	"BR-O-05": "'Not subject to VAT' lines must not carry a VAT rate.",
	"BR-O-08": "The 'not subject to VAT' taxable amount does not match the sum of its lines, charges and discounts.",
	"BR-O-09": "The 'not subject to VAT' VAT amount must be zero.",
	"BR-O-10": "A 'not subject to VAT' breakdown must state a matching exemption reason.",
	"BR-O-11": "A 'not subject to VAT' invoice cannot mix in other VAT categories.",
	"BR-O-12": "A 'not subject to VAT' invoice cannot have lines with other VAT categories.",
	"BR-O-13": "A 'not subject to VAT' invoice cannot have discounts with other VAT categories.",
	"BR-O-14": "A 'not subject to VAT' invoice cannot have charges with other VAT categories.",
	# --- PEPPOL BIS Billing 3.0 rules ---
	"PEPPOL-EN16931-R001": "A business process identifier is required.",
	"PEPPOL-EN16931-R002": "Only one document-level note is allowed (unless both parties are German organizations).",
	"PEPPOL-EN16931-R003": "A buyer reference or a purchase order number is required.",
	"PEPPOL-EN16931-R004": "The specification identifier must be the PEPPOL BIS Billing 3.0 value.",
	"PEPPOL-EN16931-R005": "The VAT accounting currency must differ from the invoice currency.",
	"PEPPOL-EN16931-R007": "The business process must follow the format 'urn:fdc:peppol.eu:2017:poacc:billing:NN:1.0'.",
	"PEPPOL-EN16931-R010": "A buyer electronic address is required.",
	"PEPPOL-EN16931-R020": "A seller electronic address is required.",
	"PEPPOL-EN16931-R040": "An allowance/charge amount must equal base amount times percentage divided by 100.",
	"PEPPOL-EN16931-R041": "An allowance/charge base amount is required when a percentage is given.",
	"PEPPOL-EN16931-R042": "An allowance/charge percentage is required when a base amount is given.",
	"PEPPOL-EN16931-R043": "The charge indicator must be 'true' or 'false'.",
	"PEPPOL-EN16931-R044": "Charges are not allowed at the price level.",
	"PEPPOL-EN16931-R046": "The item net price must equal the gross price minus the price discount.",
	"PEPPOL-EN16931-R051": "All amounts must use the invoice currency (except the VAT total in accounting currency).",
	"PEPPOL-EN16931-R053": "Only one tax total with subtotals is allowed.",
	"PEPPOL-EN16931-R054": "Only one tax total without subtotals is allowed when a tax currency is set.",
	"PEPPOL-EN16931-R055": "The VAT total and the VAT total in accounting currency must have the same sign.",
	"PEPPOL-EN16931-R061": "A mandate reference is required for direct debit payments.",
	"PEPPOL-EN16931-R080": "Only one project reference is allowed at document level.",
	"PEPPOL-EN16931-R110": "A line period start date must fall within the invoicing period.",
	"PEPPOL-EN16931-R111": "A line period end date must fall within the invoicing period.",
	"PEPPOL-COMMON-R040": "The GLN must be in a valid GS1 format.",
	"PEPPOL-COMMON-R049": "The Swedish organization number format is invalid.",
	"PEPPOL-COMMON-R050": "The Australian Business Number (ABN) format is invalid.",
}


def get_friendly_message(code: str | None) -> str | None:
	"""
	Return the translated, plain-language explanation for a rule code, or None
	when no mapping exists (callers should fall back to the raw technical text).
	"""
	if not code:
		return None
	source = PEPPOL_RULE_MESSAGES.get(code)
	return _(source) if source else None


def build_validation_report(messages: list[dict]) -> str:
	"""
	Render validation messages as HTML: a plain-language list up front, with the
	raw rule codes and technical text grouped in a single collapsed section.

	Args:
		messages: list of {"severity", "code", "message"} dicts as stored in the
			EDocument "validation_details" field.

	Returns:
		str: HTML markup, or an empty string when there are no messages.
	"""
	if not messages:
		return ""

	# Errors first, warnings second, preserving order within each group.
	errors = [m for m in messages if m.get("severity") != "warning"]
	warnings = [m for m in messages if m.get("severity") == "warning"]
	ordered = errors + warnings

	friendly_rows = []
	technical_rows = []
	for message in ordered:
		severity = message.get("severity") or "error"
		code = message.get("code")
		technical = message.get("message") or ""
		friendly = get_friendly_message(code) or technical

		pill = "red" if severity != "warning" else "orange"
		label = _("Error") if severity != "warning" else _("Warning")
		friendly_rows.append(
			f'<div style="margin-bottom:8px;">'
			f'<span class="indicator-pill {pill}">{escape_html(label)}</span> '
			f"<span>{escape_html(friendly)}</span>"
			f"</div>"
		)

		# Each row is escaped here (code + technical text); the joined block is NOT
		# escaped again below, otherwise the entities would be double-encoded.
		code_label = f"[{escape_html(code)}] " if code else ""
		technical_rows.append(f"{code_label}{escape_html(technical)}")

	summary = _("{0} error(s), {1} warning(s)").format(len(errors), len(warnings))

	technical_block = (
		'<details style="margin-top:12px;">'
		f'<summary style="cursor:pointer;">{escape_html(_("Show technical details"))}</summary>'
		'<div style="margin-top:8px;padding:8px;background:var(--control-bg, #f4f5f6);'
		"border-radius:6px;font-family:monospace;font-size:12px;white-space:pre-wrap;"
		'word-break:break-word;">' + "\n".join(technical_rows) + "</div>"
		"</details>"
	)

	return (
		'<div class="edocument-validation-report">'
		f'<div style="margin-bottom:10px;color:var(--text-muted);">{escape_html(summary)}</div>'
		+ "".join(friendly_rows)
		+ technical_block
		+ "</div>"
	)
