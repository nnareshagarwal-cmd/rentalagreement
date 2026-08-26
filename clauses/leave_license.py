CLAUSES = [
    {
        "id": "grant_of_licence",
        "title": "GRANT OF LICENCE",
        "text": "The {licensor_word} hereby permits and grants license and the {licensee_word} hereby accepts to use as the said premises for the purpose of Residential use for a term of 11 months on leave and license basis. The license period shall be deemed to have commenced {agreement_start_date} to {agreement_end_date}. NOTICE PERIOD mentioned in below point needs to be served, irrespective of agreement expiry date",
        "locked": True,
        "condition": None
    },
    {
        "id": "license_charges___compensation",
        "title": "LICENSE CHARGES / COMPENSATION",
        "text": "The {licensee_word} shall pay advance license charges of an amount of Rs. {monthly_rent} ({monthly_rent_words}) per month {maintenance} Maintenance for the 11 months for the use of the said premises.",
        "locked": True,
        "condition": None
    },
    {
        "id": "default_in_license_charges___compensation",
        "title": "DEFAULT IN LICENSE CHARGES / COMPENSATION",
        "text": "That in the event of there being default in payment of monthly rent amount for any 1 (one) month, the {licensor_word} shall have right to recover possession of the Schedule Property by resorting to the necessary proceedings and shall have the right to forfeit this agreement of the {licensee_word} on the ground of default in the payment of the rent or LICENSE CHARGES / COMPENSATION.",
        "locked": True,
        "condition": None
    },
    {
        "id": "apartment_complex_or_society_maintenance",
        "title": "APARTMENT COMPLEX OR SOCIETY MAINTENANCE",
        "text": "Maintenance to be paid to the society or to the {licensor_word} as directed by the {licensor_word}. The maintenance amount is subject to change during the term of the agreement as decided by the society association and {licensee_word} needs to pay the changed amount as directed by society association.",
        "locked": False,
        "condition": None
    },
    {
        "id": "payment_of_license_charges",
        "title": "PAYMENT OF LICENSE CHARGES",
        "text": "The {licensee_word} shall pay the said monthly license in advance on or before 5th of each month according to English calendar and shall not commit default in paying the same. Payment shall be done through online banking.",
        "locked": False,
        "condition": None
    },
    {
        "id": "renewal",
        "title": "RENEWAL",
        "text": "That agreement may be renewed for the next period of 11 months with {increase_percent} increment in license fees and at other terms to be mutually decided thereon. However, that if the {licensor_word} does not wish to renew this agreement, the {licensee_word} has agreed to vacate the premises immediately upon expiry, or sooner, and in good faith hand over the peaceful possession back to the {licensor_word}.",
        "locked": False,
        "condition": None
    },
    {
        "id": "security_deposit",
        "title": "SECURITY DEPOSIT",
        "text": "For the grant of the {licensee_word} has paid on the execution of this agreement an amount of Rs. {security_deposit} ({security_deposit_words}) to the {licensor_word} as a refundable security deposit towards the grant of the license. The {licensor_word} admits and acknowledges the receipt of the said amount. No Interest is paid on the said security deposit. Security Deposit cannot be used to adjust LICENSE CHARGES / COMPENSATION at any point.",
        "locked": True,
        "condition": None
    },
    {
        "id": "lock_in",
        "title": "LOCK IN",
        "text": "There will be Lock in period of {lockin_months} Months starting from {agreement_start_date} to {lockin_end_date}. If {licensee_word} vacates before {lockin_months} months, {penalty_deduction} days of monthly rent will be deducted from deposit and will not be refunded back to {licensee_word}. It is mandatory to provide {notice_period} of notice period to {licensor_word} before vacating the property.  If no notice is provided, complete deposit is forfeited and would not be refunded.",
        "locked": True,
        "condition": None
    },
    {
        "id": "notice_period",
        "title": "NOTICE PERIOD",
        "text": "The {licensor_word} or {licensee_word} are entitled to terminate this agreement by providing {notice_period} of notice after completion of Lock in Period. Failure to give {notice_period} notice makes {licensee_word} pay {notice_period} of rent to {licensor_word}. Rent needs to be paid during the notice period and cannot be adjusted from Deposit.",
        "locked": True,
        "condition": None
    },
    {
        "id": "pets",
        "title": "PETS",
        "text": "Not allowed within the property.",
        "locked": False,
        "condition": None
    },
    {
        "id": "smoking",
        "title": "SMOKING",
        "text": "Not allowed within the property.",
        "locked": False,
        "condition": None
    },
    {
        "id": "single_point_of_contact",
        "title": "SINGLE POINT OF CONTACT (Roles and Responsibility)",
        "text": "\na) {tenant_poc} will be single point of contact for {licensor_word} and his/her authorized representative.\n\nb) {tenant_poc} will be responsible for paying LICENSE CHARGES / COMPENSATION on time. If any one of the {licensee_word} vacates the said premises, LICENSE CHARGES / COMPENSATION will not be reduced and needs to be paid in full to {licensor_word}.\n\nc) That if there is any change in {licensee_word}, {tenant_poc} needs to inform {licensor_word} or his/her representative and new agreement will be drawn with all the {licensee_word} and charges for {licensee_word} verification for newly added {licensee_word} and agreement which will be 2,500 (Two Thousand and Five Hundred only) need to be paid by new {licensee_word} or managed by {tenant_poc}. Complete Inspection of the room and common areas will be done whenever there is a change of {licensee_word} in that room and any damages needs to be borne by all {licensee_word} or respective tenant as decided by {tenant_poc}.\n\nd) If {tenant_poc} is vacating the said premises then he/she needs to find his/her replacement too and introduce next Point of contact to {licensor_word} and assign all roles and responsibility of the said premises to the new point of contact.",
        "locked": False,
        "condition": "tenant_type == 'bachelor'"
    },
    {
        "id": "opposite_gender",
        "title": "",
        "text": "Opposite Gender ({opp_gender}) are not allowed as roommates. And no more than 3 {tenant_gender} Roommates are allowed as permanent member in the flat.",
        "locked": False,
        "condition": "tenant_type == 'bachelor'"
    },
    {
        "id": "electricity_and_water_charges",
        "title": "ELECTRICITY & WATER CHARGES",
        "text": "That is addition to the monthly compensation as aforesaid the {licensee_word} shall pay the electricity and water charges as per the reading of the meters to the appropriate authorities regularly, failing which the {licensor_word} has every right to terminate the present agreement.",
        "locked": False,
        "condition": None
    },
    {
        "id": "taxes",
        "title": "TAXES",
        "text": "The municipal/property taxes in respect of the said premises shall be borne and paid by the {licensor_word} alone.",
        "locked": False,
        "condition": None
    },
    {
        "id": "subletting",
        "title": "SUBLETTING",
        "text": "That the {licensee_word} shall not be entitled to sublet the said premises to any other person/s or organization/s and shall use it exclusively only for residential purpose and cannot be used for any commercial purpose. {licensee_word} cannot take any GST registration on this property.",
        "locked": False,
        "condition": None
    },
    {
        "id": "deduction_of_rent_amount_for_repairs",
        "title": "DEDUCTION OF RENT AMOUNT FOR REPAIRS",
        "text": "The {licensee_word} should never deduct any amount from the monthly rent payment without {licensor_word} or his/her authorized representative confirmation. If this is done without confirmation, it will be breach of clauses of the signed agreement which can lead to termination of the agreement and property vacate notice.",
        "locked": False,
        "condition": None
    },
    {
        "id": "repairs",
        "title": "REPAIRS",
        "text": "The {licensee_word} shall not do any act whereby the said premises or its fixtures or fittings are damaged. The {licensee_word} shall maintain the premises in a proper condition and shall be liable to rectify and repair the said premises in case of any damage is caused to the same due to the acts or use of the {licensee_word} and in case the {licensee_word} fails to rectify / repair the same then in such case the {licensor_word} shall be entitled to claim the damages and shall deduct the damages from the amount kept as security deposit. If the damages are more than the security deposit which is kept with the {licensor_word}, the {licensor_word} is entitled to recover all the amount from the {licensee_word} and the {licensee_word} has accepted and acknowledge the same. Any day to day repair for electrical, plumbing and carpentry needs to be take care by {licensee_word} at their own cost as these are part of regular wear and tear and should be fixed by {licensee_word}. This covers lights, Fans, Taps, showers, flush system, health faucets, cupboards hinges and channels whose regular repairs and replacements if not working needs to be done by {licensee_word} at his/her own cost. If there are any appliances in the house like ACs, Geysers, Chimney, etc then those also needs to be regularly serviced or repaired by {licensee_word} to keep in working condition.",
        "locked": False,
        "condition": None
    },
    {
        "id": "painting_and_cleaning",
        "title": "PAINTING AND CLEANING",
        "text": "{licensee_word} needs to make sure there are no marks on walls while handover and professionally cleaned in the same state while handover back to {licensor_word} or his/her authorized representatives. If any marks are there, then {licensee_word} needs to paint and handover. Failure to this will result in deduction of the amount from the Deposit.",
        "locked": False,
        "condition": None
    },
    {
        "id": "inspection",
        "title": "INSPECTION",
        "text": "That the {licensor_word} or his/her authorized representative shall be entitled to inspect the said premises and take pictures of the complete premises along with issues or repairs required within the premises, which will shared with the {licensor_word} to help him understand how the said premises is maintained by the {licensee_word}. Prior intimation and approval of the {licensee_word} will be taken to schedule the inspection. The {licensee_word} shall keep all fixtures, electric fittings, water connections in good running condition.",
        "locked": False,
        "condition": None
    },
    {
        "id": "breakage",
        "title": "BREAKAGE",
        "text": "That the {licensee_word} shall be responsible for any breakage to the said premises or fixtures and fittings therein, occurring during the period of license except due to ordinary climate or atmospheric wear and tear or causes beyond {licensee_word}’s control and natural calamities.",
        "locked": False,
        "condition": None
    },
    {
        "id": "alteration",
        "title": "ALTERATION",
        "text": "That the {licensee_word} shall not be entitled to make any kind of alteration or addition in the said premises except with the written prior consent of the {licensor_word}. No Nails on any walls or wall mounting or change of color or any kind of wallpaper is not allowed. If still {licensee_word} needs it, required permission is needed from {licensor_word} or his/her authorized representative.",
        "locked": False,
        "condition": None
    },
    {
        "id": "forfeiture",
        "title": "FORFEITURE",
        "text": "The {licensee_word} covenants with the {licensor_word} that all rights granted under this License shall be subject to forfeiture in the event of any breach of its terms, including but not limited to non-payment of monthly compensation, unauthorized subletting, damage to the premises, or failure to maintain the property. In such circumstances, the {licensor_word} shall have the right to immediately resume possession of the premises, and the Lock-in Period clause shall stand terminated.",
        "locked": False,
        "condition": None
    },
    {
        "id": "judicial_possession",
        "title": "JUDICIAL POSSESSION",
        "text": "That at all times, the judicial possession of the said premises shall be of the {licensor_word}. The {licensee_word} has been merely granted permission to use the said premises and fixtures and fittings on leave and license basis and the {licensee_word} shall hand it over on the expiry of the stipulated period, unless it has been renewed, extended or changed mutually by and between the parties.",
        "locked": False,
        "condition": None
    },
    {
        "id": "to_keep_the_premises_clean_and_tidy",
        "title": "TO KEEP THE PREMISES CLEAN AND TIDY",
        "text": "That the {licensee_word} should keep the said premises clean and tidy and use the premises for which purpose it is given.",
        "locked": False,
        "condition": None
    },
    {
        "id": "licensees_not_entitled_to_assign",
        "title": "{licensee_word} NOT ENTITLED TO ASSIGN",
        "text": "The {licensee_word} shall not assign, transfer, sub-license or part with the said premises or any part thereof, in any manner whatsoever, at any time during the continuance of this agreement or thereafter.",
        "locked": False,
        "condition": None
    },
    {
        "id": "nuisance_and_annoyance",
        "title": "NUISANCE & ANNOYANCE",
        "text": "The {licensee_word} shall not do or cause to do or permit to do any act which would amount to nuisance or annoyance to the neighboring occupiers and shall not do or permit to do any immoral acts in the said premises and shall not do any act, deed or thing whereby the {licensor_word} suffers any loss or damage or which may cause disturbance to the {licensor_word} or to the neighboring occupiers.",
        "locked": False,
        "condition": None
    },
    {
        "id": "licensees_shall_abide_by_law",
        "title": "{licensee_word} SHALL ABIDE BY LAW",
        "text": "The {licensee_word} shall not do anything which is not permissible or which is prohibited under the law or is in contravention of any bye- law, rules and regulations or any order.",
        "locked": False,
        "condition": None
    },
    {
        "id": "premise_free_from_encumbrances",
        "title": "PREMISE FREE FROM ENCUMBRANCES",
        "text": "The {licensor_word} hereby declares that the said premise is free from all encumbrances and there is no hindrance for the {licensor_word} to grant this license to {licensee_word}.",
        "locked": False,
        "condition": None
    },
    {
        "id": "termination_by_licensor",
        "title": "TERMINATION BY {licensor_word}",
        "text": "Before the expiry of the period of license, the {licensor_word} is entitled to terminate the license of the {licensee_word} with a {notice_period} written notice in advance to the {licensee_word}. License charges or compensation needs to be paid during notice period and cannot be adjusted from Security Deposit.",
        "locked": True,
        "condition": None
    },
    {
        "id": "termination_by_licensees",
        "title": "TERMINATION BY {licensee_word}",
        "text": "If the {licensee_word} intends to vacate or terminate the said Premises before the expiry of license period, he shall first give {notice_period} notice, after completion of Lock in Period, in writing to the {licensor_word} informing of his intention for vacating and termination of this agreement. On the expiry of such notice the {licensee_word} shall vacate the said premises and this agreement shall stand terminated. Failure to give {notice_period} notice makes {licensee_word} pay {notice_period} compensation to the {licensor_word}. License charges or compensation needs to be paid during notice period and cannot be adjusted from Security Deposit.",
        "locked": True,
        "condition": None
    },
    {
        "id": "to_vacate",
        "title": "TO VACATE",
        "text": "Upon termination of the license or upon the expiry of the License period, if the agreement is not renewed, the {licensee_word} shall quit, and vacate the said premises on or before the expiry of the period of this license agreement i.e. on or before {agreement_end_date}, if the agreement is not renewed.",
        "locked": False,
        "condition": None
    },
    {
        "id": "refund_of_security_deposit",
        "title": "REFUND OF SECURITY DEPOSIT",
        "text": "The {licensor_word} shall refund the amount of the security deposit to the {licensee_word} on vacation of the said premises by the {licensee_word}, subject to the deductions of any amount recoverable from the {licensee_word} under this agreement. The {licensor_word} shall refund this amount to the {licensee_word} within 15 days of the {licensee_word} vacating the property. License charges or compensation needs to be paid during notice period and cannot be adjusted from Security Deposit.",
        "locked": True,
        "condition": None
    },
    {
        "id": "remedy_against_the_licensees",
        "title": "REMEDY AGAINST THE {licensee_word}",
        "text": "If the {licensee_word} fails to quit and vacate the said premises of the {licensor_word} then in such a situation, the {licensor_word} has the right to institute a suit for ejection against the {licensee_word} for not vacating the property. The {licensor_word} shall be entitled to forfeit the security deposit amount and proceed to recover possession from the {licensee_word} in the court.",
        "locked": False,
        "condition": None
    },
    {
        "id": "right_to_vacate",
        "title": "RIGHT TO VACATE",
        "text": "Upon termination of the license or upon expiry of the license period the {licensee_word} shall not be entitled to enter upon the said premises, except for removing his/her belongings etc. and the {licensor_word} shall be entitled to a free and unobstructed access to the said premises, including the right of breaking open of the locks etc. and removing the belongings/articles/persons etc. of the {licensee_word} from the said premises and vacate the premises and it shall be deemed as if the {licensor_word} has been specifically irrevocably empowered, authorized and consented by the {licensee_word} to remove the properties etc. from The said premises and take possession. All the costs of such vacation shall be recoverable by the {licensor_word} and till the said costs are paid the {licensor_word} shall have a lien on the Property/belonging etc. as may have been removed from the said premises.",
        "locked": False,
        "condition": None
    },
    {
        "id": "no_claim_of_tenancy",
        "title": "NO CLAIM OF TENANCY",
        "text": "It is clearly understood between the parties to this agreement that no relationship of {licensor_word} and {licensee_word} exists between them and that the {licensor_word} has not granted tenancy rights in the said premises to the {licensee_word} by this agreement. The {licensee_word} shall not make any claim of tenancy in the said premises.",
        "locked": False,
        "condition": None
    },
    {
        "id": "address_for_communication",
        "title": "ADDRESS FOR COMMUNICATION",
        "text": "That any communication made by and between parties at the address mentioned above shall deemed to have been duly received in due course of time.",
        "locked": False,
        "condition": None
    },
    {
        "id": "partnership",
        "title": "PARTNERSHIP",
        "text": "Nothing herein contained shall constitute a partnership or a joint venture or any other relationship between the parties except that of the {licensor_word} and {licensee_word}.",
        "locked": False,
        "condition": None
    },
    {
        "id": "no_waiver",
        "title": "NO WAIVER",
        "text": "It is agreed that any indulgence shown or any delay on the part",
        "locked": False,
        "condition": None
    },
    {
        "id": "free_consent",
        "title": "FREE CONSENT",
        "text": "The {licensee_word} has duly executed this agreement after clearly understanding the implications and consequences of the agreement and they have signed hereunder by their free will and free consent",
        "locked": False,
        "condition": None
    },
    {
        "id": "thefts_or_loss",
        "title": "THEFTS OR LOSS",
        "text": "{licensor_word} shall not be responsible or liable for any theft or",
        "locked": False,
        "condition": None
    },
    {
        "id": "vacation_tips",
        "title": "VACATION TIPS",
        "text": "{licensee_word} has to follow following tips if they are going out of the city or not available in the premises for longer duration.\na. Isolate the Energy Sources like Electrical and Gas with the help of maintenance team.\nb. Shut off the Gas connection from Mains and all electrical appliances and keep flammable material away from ignition sources.\nc. Shut off the main inlet valves of water supply pipelines.\nd. If you have to leave any appliance switched 'ON' during your absence e.g. Refrigerator... ensure the surrounding area is free from any combustible material and is well ventilated to allow heat dissipation.\ne. DO NOT leave any appliances in 'AUTO' mode e.g. Dish/Clothes Washing Machines.",
        "locked": False,
        "condition": None
    },
    {
        "id": "stamp_paper_possession",
        "title": "STAMP PAPER POSSESSION",
        "text": "The parties hereto have executed this license on stamp paper the original license shall remain with {licensor_word} & copy thereof with {licensee_word}.",
        "locked": False,
        "condition": None
    },
    {
        "id": "deep_cleaning",
        "title": "DEEP CLEANING",
        "text": "The house should be deep cleaned by the {licensee_word} at his/her cost at the time of vacating the apartment.",
        "locked": False,
        "condition": None
    },
    {
        "id": "key_return_and_refund",
        "title": "KEY RETURN & REFUND",
        "text": "The advance deposit will be refunded to the {licensee_word} only after the {licensee_word} returns all the original keys given to him at the time of moving in, and after deducting any repair, cleaning and pending utilities or society charges.",
        "locked": False,
        "condition": None
    },
    {
        "id": "jurisdiction",
        "title": "JURISDICTION",
        "text": "All or any disputes arising out of or in connection with this agreement shall be subject to the jurisdiction of the courts in {property_city} only.",
        "locked": False,
        "condition": None
    },
    {
        "id": "fittings_and_fixtures_maintenance",
        "title": "FITTINGS & FIXTURES MAINTENANCE",
        "text": "The {licensee_word} will ensure all the fittings and fixtures (lights, fans, geysers, shelves, cabinets, taps, etc.) in the house are in a proper working condition during {pronoun_his} stay and until {pronoun_they} vacates the property.",
        "locked": False,
        "condition": None
    },
    {
        "id": "move_in_out_charges",
        "title": "MOVE IN / MOVE OUT CHARGES",
        "text": "The {licensee_word} should pay the move in / Move out charges to the society, as per the society regulations.",
        "locked": False,
        "condition": None
    },
    {
        "id": "address_proof_restriction",
        "title": "ADDRESS PROOF RESTRICTION",
        "text": "The {licensee_word} shall not use the address of the licensed premises for updating, registering, or linking any government identity or address records. In particular, the {licensee_word} shall not use the premises address for address update in Aadhaar or the Indian Passport.",
        "locked": False,
        "condition": None
    },
    {
        "id": "description_of_the_said_premises",
        "title": "DESCRIPTION OF THE SAID PREMISES",
        "text": "",
        "locked": False,
        "condition": None
    },
    {
        "id": "licensor",
        "title": "{licensor_word}",
        "text": "",
        "locked": False,
        "condition": None
    },
    {
        "id": "licensees",
        "title": "{licensee_word}",
        "text": "",
        "locked": False,
        "condition": None
    },
]
