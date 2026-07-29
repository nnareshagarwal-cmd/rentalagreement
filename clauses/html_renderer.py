"""
clauses/html_renderer.py — Live HTML Preview Generator for Web UI
===================================================================
"""

import sys, os
import html as _html

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from .leave_license import CLAUSES as LEAVE_LICENSE_CLAUSES
from .simple_rental import CLAUSES as SIMPLE_RENTAL_CLAUSES
from .formatters import _safe_int, _html_bold_targets, _is_leave_license, _should_skip_clause
from .evaluator import _resolve_value, _build_field_map, _evaluate_clause, _substitute_fields

def _get_preamble_paragraphs(data, field_map, agreement_type):
    owner_count = _safe_int(_resolve_value(data, "owner_count") or "1")
    tenant_count = _safe_int(_resolve_value(data, "tenant_count") or "1")
    
    owners_list = []
    for i in range(1, owner_count + 1):
        name = field_map.get(f"{{owner{i}_name}}", "")
        age = field_map.get(f"{{owner{i}_age}}", "")
        careof_abbr = field_map.get(f"{{owner{i}_careof}}", "S")
        careofname = field_map.get(f"{{owner{i}_careofname}}", "")
        occ = field_map.get(f"{{owner{i}_occupation}}", "")
        addr = field_map.get(f"{{owner{i}_address}}", "")
        
        owners_list.append(
            f"Name: {name}\n"
            f"Age: {age} years\n"
            f"{careof_abbr}/o: {careofname}\n"
            f"Occupation: {occ}\n"
            f"Address: {addr}"
        )
    
    tenants_list = []
    for i in range(1, tenant_count + 1):
        name = field_map.get(f"{{tenant{i}_name}}", "")
        age = field_map.get(f"{{tenant{i}_age}}", "")
        careof_abbr = field_map.get(f"{{tenant{i}_careof}}", "S")
        careofname = field_map.get(f"{{tenant{i}_careofname}}", "")
        occ = field_map.get(f"{{tenant{i}_occupation}}", "")
        addr = field_map.get(f"{{tenant{i}_address}}", "")
        
        tenants_list.append(
            f"Name: {name}\n"
            f"Age: {age} years\n"
            f"{careof_abbr}/o: {careofname}\n"
            f"Occupation: {occ}\n"
            f"Address: {addr}"
        )
    
    prop_address = field_map.get("{property_address}", "")
    start_date = field_map.get("{agreement_start_date}", "")
    end_date = field_map.get("{agreement_end_date}", "")
    agreement_date = field_map.get("{agreement_date}", "")
    
    if _is_leave_license(agreement_type):
        licensor_label = "OWNERS" if owner_count > 1 else "OWNER"
        licensor_word = "LICENSORS" if owner_count > 1 else "LICENSOR"
        licensee_word = "LICENSEES" if tenant_count > 1 else "LICENSEE"
        
        paras = [
            f"THIS AGREEMENT OF LEAVE AND LICENCE MADE ON THIS date of \n{agreement_date}, AT HYDERABAD",
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
            f"THIS RENTAL AGREEMENT is made and executed on this date of \n{agreement_date}, AT HYDERABAD",
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
    
    bold_targets = [v for k, v in field_map.items() if v and len(str(v).strip()) > 1]
    
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
            
        html_parts.append(f'<div class="clause-block"><p class="clause-text" style="{style}">{inner_content}</p></div>')
        
    num = 1
    for clause in clause_defs:
        if _should_skip_clause(clause, agr_type):
            continue
            
        evaluated_text = _evaluate_clause(clause, data)
        if evaluated_text is None:
            continue
            
        substituted_text = _substitute_fields(evaluated_text, field_map)
        
        escaped_text = _html.escape(substituted_text)
        bolded_text = _html_bold_targets(escaped_text, bold_targets)
        
        title_str = f"<b>{_html.escape(clause['title'])}</b>: " if clause.get('title') else ""
        num_prefix = f"<b>{num}.</b> " if not is_ll else ""
        
        c_id = clause['id']
        html_parts.append(
            f'<div class="clause-block" data-clause-id="{c_id}">'
            f'<p class="clause-text">{num_prefix}{title_str}{bolded_text}</p>'
            f'</div>'
        )
        num += 1
        
    return "\n".join(html_parts)
