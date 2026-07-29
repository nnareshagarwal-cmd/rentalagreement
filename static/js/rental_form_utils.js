/* rental_form_utils.js - Pure utility functions for rental form */

// Format numbers with Indian separators (e.g., 1,50,000)
function formatIndianNumber(num) {
    if (!num) return '';
    const digits = String(num).replace(/\D/g, '');
    if (!digits) return '';
    if (digits.length <= 3) return digits;
    let result = '';
    let count = 0;
    for (let i = digits.length - 1; i >= 0; i--) {
        if (count === 3 || (count > 3 && (count - 3) % 2 === 0)) {
            result = ',' + result;
        }
        result = digits[i] + result;
        count++;
    }
    return result;
}

// Convert numbers to words (Indian numbering: Lakh, Crore)
function numberToWords(num) {
    const cleaned = String(num).replace(/,/g, '').trim();
    if (!cleaned || isNaN(cleaned)) return '';
    num = parseInt(cleaned, 10);
    if (num === 0) return 'Zero';
    const ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine'];
    const teens = ['Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen'];
    const tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'];
    function convertBelowThousand(n) {
        let result = '';
        const hundreds = Math.floor(n / 100);
        if (hundreds > 0) result += ones[hundreds] + ' Hundred ';
        const remainder = n % 100;
        if (remainder >= 20) {
            const tensDigit = Math.floor(remainder / 10);
            const onesDigit = remainder % 10;
            result += tens[tensDigit];
            if (onesDigit > 0) result += ' ' + ones[onesDigit];
        } else if (remainder >= 10) {
            result += teens[remainder - 10];
        } else if (remainder > 0) {
            result += ones[remainder];
        }
        return result.trim();
    }
    if (num < 0) return 'Negative ' + numberToWords(-num);
    let words = '';
    const crore = Math.floor(num / 10000000);
    if (crore > 0) {
        words += convertBelowThousand(crore) + ' Crore ';
        num = num % 10000000;
    }
    const lakh = Math.floor(num / 100000);
    if (lakh > 0) {
        words += convertBelowThousand(lakh) + ' Lakh ';
        num = num % 100000;
    }
    const thousand = Math.floor(num / 1000);
    if (thousand > 0) {
        words += convertBelowThousand(thousand) + ' Thousand ';
        num = num % 1000;
    }
    if (num > 0) {
        words += convertBelowThousand(num) + ' ';
    }
    return words.trim();
}

// Calculate agreement end date (start + 11 months - 1 day)
function calculateEndDate(startDateStr) {
    if (!startDateStr) return '';
    try {
        const startDate = new Date(startDateStr);
        if (isNaN(startDate.getTime())) return '';
        let endDate = new Date(startDate);
        endDate.setMonth(endDate.getMonth() + 11);
        endDate.setDate(endDate.getDate() - 1);
        const year = endDate.getFullYear();
        const month = String(endDate.getMonth() + 1).padStart(2, '0');
        const day = String(endDate.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    } catch (e) {
        return '';
    }
}
