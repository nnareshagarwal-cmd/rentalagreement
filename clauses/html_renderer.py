"""
clauses/html_renderer.py — Live HTML Preview Generator for Web UI
===================================================================
"""

import sys, os
import html as _html

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from .leave_license import CLAUSES as LEAVE_LICENSE_CLAUSES
from .simple_rental import CLAUSES as SIMPLE_RENTAL_CLAUSES
from .formatters import (
    _safe_int, _html_bold_targets, _is_leave_license, _should_skip_clause,
    combine_name_prefix_once, format_age, format_careof
)
from .evaluator import _resolve_value, _build_field_map, _evaluate_clause, _substitute_fields

def _get_preamble_paragraphs(data, field_map, agreement_type):
    owner_count = _safe_int(_resolve_value(data, "owner_count") or "1")
    tenant_count = _safe_int(_resolve_value(data, "tenant_count") or "1")
    
    owners_list = []
    for i in range(1, owner_count + 1):
        name = field_map.get(f"{{owner{i}_name}}") or combine_name_prefix_once(_resolve_value(data, f"owner{i}_prefix"), _resolve_value(data, f"owner{i}_name"))
        age = field_map.get(f"{{owner{i}_age}}") or format_age(_resolve_value(data, f"owner{i}_age"))
        careof_abbr = field_map.get(f"{{owner{i}_careof}}") or format_careof(_resolve_value(data, f"owner{i}_prefix"), _resolve_value(data, f"owner{i}_careof"))
        careofname = field_map.get(f"{{owner{i}_careofname}}") or combine_name_prefix_once(_resolve_value(data, f"owner{i}_careofname_prefix") or "Mr.", _resolve_value(data, f"owner{i}_careofname"))
        occ = field_map.get(f"{{owner{i}_occupation}}") or _resolve_value(data, f"owner{i}_occupation")
        addr = field_map.get(f"{{owner{i}_address}}") or _resolve_value(data, f"owner{i}_address").upper()
        
        owners_list.append(
            f"Name: {name}\n"
            f"Age: {age} years\n"
            f"{careof_abbr}/o: {careofname}\n"
            f"Occupation: {occ}\n"
            f"Address: {addr}"
        )
    
    tenants_list = []
    for i in range(1, tenant_count + 1):
        name = field_map.get(f"{{tenant{i}_name}}") or combine_name_prefix_once(_resolve_value(data, f"tenant{i}_prefix"), _resolve_value(data, f"tenant{i}_name"))
        age = field_map.get(f"{{tenant{i}_age}}") or format_age(_resolve_value(data, f"tenant{i}_age"))
        careof_abbr = field_map.get(f"{{tenant{i}_careof}}") or format_careof(_resolve_value(data, f"tenant{i}_prefix"), _resolve_value(data, f"tenant{i}_careof"))
        careofname = field_map.get(f"{{tenant{i}_careofname}}") or combine_name_prefix_once(_resolve_value(data, f"tenant{i}_careofname_prefix") or "Mr.", _resolve_value(data, f"tenant{i}_careofname"))
        occ = field_map.get(f"{{tenant{i}_occupation}}") or _resolve_value(data, f"tenant{i}_occupation")
        addr = field_map.get(f"{{tenant{i}_address}}") or _resolve_value(data, f"tenant{i}_address").upper()
        
        tenants_list.append(
            f"Name: {name}\n"
            f"Age: {age} years\n"
            f"{careof_abbr}/o: {careofname}\n"
            f"Occupation: {occ}\n"
            f"Address: {addr}"
        )
    
    prop_address = field_map.get("{property_address}", "")
    prop_city = (field_map.get("{property_city}") or "HYDERABAD").upper()
    start_date = field_map.get("{agreement_start_date}", "")
    end_date = field_map.get("{agreement_end_date}", "")
    agreement_date = field_map.get("{agreement_date}", "")
    
    if _is_leave_license(agreement_type):
        licensor_label = "OWNERS" if owner_count > 1 else "OWNER"
        licensor_word = "LICENSORS" if owner_count > 1 else "LICENSOR"
        licensee_word = "LICENSEES" if tenant_count > 1 else "LICENSEE"
        
        paras = [
            f"THIS AGREEMENT OF LEAVE AND LICENCE MADE ON THIS date of \n{agreement_date}, AT {prop_city}",
            "BETWEEN",
        ]
        paras.extend(owners_list)
        paras.append(f"Hereinafter called as \"{licensor_label}\" and / or {licensor_word} OF THE ONE PART")
        paras.append("AND")
        paras.extend(tenants_list)
        paras.extend([
            f"Here in after called as {licensee_word} OF THE OTHER PART.",
            f"WHEREAS the {licensor_word} is the lawful and legal owner and is fully seized and possessed of the premises, located at {prop_address}.",
            "This is also described in the Schedule hereunder written. The said premise is the subject matter of this license agreement (hereinafter referred to as the \"SAID PREMISES\").",
            "AND WHEREAS the party of the one part did not presently require the said premises and hence intended to give the same on leave and license basis for temporary period. The party of the other part required for residential purpose. Accordingly, the party of the other part approached the party of the one part and proposed to take the said premises for temporary period on the leave and license.",
            f"AND WHEREAS the {licensor_word} accepted the said request of the {licensee_word} and agreed to grant the said premises to the {licensee_word} on certain terms and conditions.",
            f"AND WHEREAS the party of the one part, as proposed by the {licensee_word} has agreed to grant license and allow the party of the other part to use the said premises for a period of 11 Months commencing from {start_date} to {end_date} on Leave & License basis on the following terms and conditions.",
            "NOW THEREFORE THIS AGREEMENT WITNESSES AND IT IS HEREBY AGREED BY AND BETWEEN THE PARTIES AS UNDER:"
        ])
        return paras
    else:
        owner_label = "OWNERS" if owner_count > 1 else "OWNER"
        owner_title = "Absolute Owners" if owner_count > 1 else "Absolute Owner"
        tenant_label = "TENANTS" if tenant_count > 1 else "TENANT"
        tenant_word = "Tenants" if tenant_count > 1 else "Tenant"

        paras = [
            f"THIS RENTAL AGREEMENT is made and executed on this date of \n{agreement_date}, AT {prop_city}",
            "BETWEEN",
        ]
        paras.extend(owners_list)
        paras.append(f"(Here in after called the “{owner_title}” which term shall mean and include his/her legal representatives, successors, administrators, etc.) Of the First party.")
        paras.append("AND")
        paras.extend(tenants_list)
        paras.extend([
            f"(Here in after called the “{tenant_label}” which term shall mean and include his/her legal representatives, successors, administrators, etc.) Of the Other party.",
            f"WHEREAS the First party is the absolute owner of the residential flat bearing address: {prop_address}",
            f"AND WHEREAS the {tenant_word} has approached the {owner_label.title()} to take the above-mentioned property on rent for a period of 11 Months commencing from {start_date} to {end_date} for residential purpose.",
            "NOW THIS AGREEMENT WITNESSETH AS FOLLOWS:"
        ])
        return paras

def generate_preview_html(data):
    """Generate HTML preview string for the web frontend."""
    agr_type = _resolve_value(data, "agreement_type") or "simple_rental"
    is_ll = _is_leave_license(agr_type)
    clause_defs = LEAVE_LICENSE_CLAUSES if is_ll else SIMPLE_RENTAL_CLAUSES
    
    field_map = _build_field_map(data)
    
    bold_targets = [
        "Owner", "Owners", "Tenant", "Tenants",
        "Licensor", "Licensors", "Licensee", "Licensees",
        "OWNER", "OWNERS", "TENANT", "TENANTS",
        "LICENSOR", "LICENSORS", "LICENSEE", "LICENSEES"
    ]
    pen_val = _resolve_value(data, "penalty_deduction")
    if pen_val:
        pen_str = str(pen_val).strip()
        bold_targets.append(pen_str)
        if not pen_str.lower().endswith("days"):
            bold_targets.append(f"{pen_str} days")
            bold_targets.append(f"{pen_str} DAYS")

    for v in field_map.values():
        if not v:
            continue
        v_str = str(v).strip()
        if len(v_str) > 1:
            bold_targets.append(v_str)
            if '\n' in v_str:
                for line_part in v_str.split('\n'):
                    line_clean = line_part.strip()
                    if len(line_clean) > 1:
                        bold_targets.append(line_clean)
    
    html_parts = []
    html_parts.append('<div style="height: 180px;"></div>')
    
    header_title = "LEAVE AND LICENSE AGREEMENT" if is_ll else "RENTAL AGREEMENT"
    html_parts.append(
        f'<h2 style="text-align: center; text-transform: uppercase; text-decoration: underline; margin-bottom: 28px;">'
        f'<u>{header_title}</u></h2>'
    )
    
    preamble_paras = _get_preamble_paragraphs(data, field_map, agr_type)
    for p in preamble_paras:
        lines = p.split('\n')
        p_html_lines = []
        for line in lines:
            escaped_line = _html.escape(line)
            bolded_line = _html_bold_targets(escaped_line, bold_targets)
            p_html_lines.append(bolded_line)
            
        inner_content = "<br>".join(p_html_lines)
        
        style = 'margin-bottom: 16px;'
        if line.strip() in ("BETWEEN", "AND"):
            style = 'text-align: center; font-weight: bold; width: 100%; display: block; margin: 14px 0 18px 0;'
        elif line.startswith("THIS RENTAL AGREEMENT") or line.startswith("THIS AGREEMENT OF LEAVE"):
            style = ''
        elif line.startswith("(Here in after called") or line.startswith("Hereinafter called"):
            style = 'margin-top: 16px; font-weight: bold;'
        elif line.startswith("NOW THEREFORE") or line.startswith("NOW THIS AGREEMENT"):
            style = 'font-weight: bold; text-decoration: underline; text-align: center; margin-top: 18px; margin-bottom: 18px; display: block; width: 100%;'
            
        html_parts.append(f'<div class="clause-block" style="margin-bottom: 14px;"><p class="clause-text" style="{style}">{inner_content}</p></div>')
        
    num = 1
    for clause in clause_defs:
        if _should_skip_clause(clause, agr_type):
            continue
            
        evaluated_text = _evaluate_clause(clause, data)
        if evaluated_text is None:
            continue
            
        substituted_text = _substitute_fields(evaluated_text, field_map)
        c_id = clause['id']
        
        if clause.get('is_header'):
            html_parts.append(
                f'<div class="clause-block section-header" data-clause-id="{c_id}" style="margin-top: 22px; margin-bottom: 10px;">'
                f'<p class="clause-text" style="font-weight: bold; font-size: 1.05em; text-decoration: underline; margin-bottom: 0;">{_html.escape(substituted_text)}</p>'
                f'</div>'
            )
            continue

        escaped_text = _html.escape(substituted_text)
        bolded_text = _html_bold_targets(escaped_text, bold_targets)
        
        title_str = f"<b>{_html.escape(clause['title'])}</b>: " if clause.get('title') else ""
        num_prefix = f"<b>{num}.</b> "
        
        html_parts.append(
            f'<div class="clause-block" data-clause-id="{c_id}" style="margin-bottom: 14px;">'
            f'<p class="clause-text" style="line-height: 1.6; margin-bottom: 0;">{num_prefix}{title_str}{bolded_text}</p>'
            f'</div>'
        )
        num += 1

    # ── CONCLUDING / SIGNATURE BLOCK ──────────────────────────────────────────
    owner_count = _safe_int(_resolve_value(data, "owner_count") or "1")
    tenant_count = _safe_int(_resolve_value(data, "tenant_count") or "1")
    
    if is_ll:
        owner_role_label = "LICENSORS" if owner_count > 1 else "LICENSOR"
        tenant_role_label = "LICENSEES" if tenant_count > 1 else "LICENSEE"
    else:
        owner_role_label = "OWNERS" if owner_count > 1 else "OWNER"
        tenant_role_label = "TENANTS" if tenant_count > 1 else "TENANT"

    prop_address = field_map.get("{property_address}", "")
    escaped_prop_addr = _html.escape(prop_address)
    bolded_prop_addr = _html_bold_targets(escaped_prop_addr, bold_targets)

    agr_date = field_map.get("{agreement_date}", "")
    escaped_agr_date = _html.escape(agr_date)
    bolded_agr_date = _html_bold_targets(escaped_agr_date, bold_targets)

    conclusion_html = []
    
    # 1. Heading: DESCRIPTION OF THE SAID PREMISES:
    conclusion_html.append(
        '<div class="clause-block" data-clause-id="conclusion_premise_heading" style="margin-top: 40px; margin-bottom: 16px; text-align: center; width: 100%;">'
        '<p class="clause-text" style="display: block !important; text-align: center; font-weight: bold; text-decoration: underline; margin: 0 auto; width: 100%;">'
        '<u>DESCRIPTION OF THE SAID PREMISES:</u></p></div>'
    )
    
    # 2. Premise Address Text
    conclusion_html.append(
        '<div class="clause-block" data-clause-id="conclusion_premise_text" style="margin-bottom: 24px; width: 100%;">'
        f'<p class="clause-text" style="display: block !important; line-height: 1.6; margin: 0; width: 100%;">'
        f'All that consisting of premises, at <b>{bolded_prop_addr}</b>.</p></div>'
    )
    
    # 3. In Witness Clause
    conclusion_html.append(
        '<div class="clause-block" data-clause-id="conclusion_witness_clause" style="margin-bottom: 32px; width: 100%;">'
        f'<p class="clause-text" style="display: block !important; line-height: 1.6; margin: 0; width: 100%;">'
        f'IN WITNESS, WHERE OF THE PARTIES TO THIS AGREEMENT HAVE SIGNED HEREUNDER ON THE AFORESAID DATE <b>{bolded_agr_date}</b></p></div>'
    )

    # 4. OWNERS / LICENSORS SECTION
    conclusion_html.append(
        '<div class="clause-block" data-clause-id="conclusion_owners_section" style="margin-bottom: 28px; width: 100%;">'
        f'<p class="clause-text" style="display: block !important; font-weight: bold; margin-bottom: 18px;">{owner_role_label}:</p>'
    )
    for i in range(1, owner_count + 1):
        o_pfx = _resolve_value(data, f"owner{i}_prefix") or ""
        o_name_raw = _resolve_value(data, f"owner{i}_name") or ""
        o_name = combine_name_prefix_once(o_pfx, o_name_raw)
        escaped_o_name = _html.escape(o_name)
        bolded_o_name = _html_bold_targets(escaped_o_name, bold_targets)
        conclusion_html.append(
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; width: 100%;">'
            f'<span>Name: <b>{bolded_o_name}</b></span>'
            f'<span style="font-weight: bold; text-align: right;">Signature</span>'
            f'</div>'
        )
    conclusion_html.append('</div>')

    # 5. TENANTS / LICENSEES SECTION
    conclusion_html.append(
        '<div class="clause-block" data-clause-id="conclusion_tenants_section" style="margin-bottom: 32px; width: 100%;">'
        f'<p class="clause-text" style="display: block !important; font-weight: bold; margin-bottom: 18px;">{tenant_role_label}:</p>'
    )
    for i in range(1, tenant_count + 1):
        t_pfx = _resolve_value(data, f"tenant{i}_prefix") or ""
        t_name_raw = _resolve_value(data, f"tenant{i}_name") or ""
        t_name = combine_name_prefix_once(t_pfx, t_name_raw)
        escaped_t_name = _html.escape(t_name)
        bolded_t_name = _html_bold_targets(escaped_t_name, bold_targets)
        conclusion_html.append(
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; width: 100%;">'
            f'<span>Name: <b>{bolded_t_name}</b></span>'
            f'<span style="font-weight: bold; text-align: right;">Signature</span>'
            f'</div>'
        )
    conclusion_html.append('</div>')

    # 6. WITNESS SECTION
    witness_header = "IN THE PRESENCE OF WITNESS" if is_ll else "IN THE PRESENCE OF WITNESS:"
    conclusion_html.append(
        '<div class="clause-block" data-clause-id="conclusion_witness_section" style="margin-top: 36px; width: 100%;">'
        f'<p class="clause-text" style="display: block !important; font-weight: bold; margin-bottom: 10px;">{witness_header}</p>'
        f'<p class="clause-text" style="display: block !important; font-weight: bold; margin-bottom: 20px;">WITNESS</p>'
        f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 28px; width: 100%;">'
        f'<span>Name:</span>'
        f'<span style="font-weight: bold; text-align: right;">Signature</span>'
        f'</div>'
        f'</div>'
    )

    html_parts.append("\n".join(conclusion_html))

    # 7. Annexure (Only rendered if specific items are listed)
    annexure = str(_resolve_value(data, "annexure") or "").strip()
    bare_keywords = {
        "none", "no inventory", "standard fixtures only", "standard fixtures only (no separate inventory)",
        "unfurnished", "un-furnished", "un furnished", "unfurnished (no separate inventory)",
        "semi-furnished", "semi furnished", "semi-furnished (no separate inventory)",
        "fully furnished", "fully-furnished", "fully furnished (no separate inventory)"
    }
    has_items = False
    if annexure and annexure.lower() not in bare_keywords:
        if ":" in annexure:
            prefix, content = annexure.split(":", 1)
            content_clean = content.strip().lower()
            if content_clean and content_clean not in bare_keywords and content_clean not in ("nil", "na", "n/a"):
                has_items = True
        else:
            has_items = True

    if has_items:
        if ":" in annexure and "\n" not in annexure:
            prefix, content = annexure.split(":", 1)
            annexure_lines = [
                f"<b>{_html.escape(prefix.strip().upper())}</b>",
                _html.escape(content.strip().upper())
            ]
        else:
            annexure_lines = [
                _html.escape(line.strip().upper()) if line.strip() else '&nbsp;'
                for line in annexure.splitlines()
            ]
        annexure_html = '<br>'.join(annexure_lines)
        html_parts.append(
            '<div class="clause-block" data-clause-id="annexure" '
            'style="margin-top: 44px; padding-top: 18px; border-top: 1px solid #000; width: 100%;">'
            '<p class="clause-text" style="display: block !important; text-align: center; '
            'font-weight: bold; text-decoration: underline; margin: 0 0 18px; width: 100%;">ANNEXURE</p>'
            f'<p class="clause-text" style="display: block !important; line-height: 1.7; margin: 0; width: 100%;">{annexure_html}</p>'
            '</div>'
        )

    return "\n".join(html_parts)
