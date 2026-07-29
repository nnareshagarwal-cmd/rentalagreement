/**
 * calculations.js — Financial & Date Calculation Helpers
 * ======================================================
 */

export function numToWords(num) {
    const a = ['', 'One ', 'Two ', 'Three ', 'Four ', 'Five ', 'Six ', 'Seven ', 'Eight ', 'Nine ', 'Ten ', 'Eleven ', 'Twelve ', 'Thirteen ', 'Fourteen ', 'Fifteen ', 'Sixteen ', 'Seventeen ', 'Eighteen ', 'Nineteen '];
    const b = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'];

    num = parseInt(num, 10);
    if (isNaN(num) || num === 0) return 'Zero';

    function inWords(n) {
        if (n < 20) return a[n];
        if (n < 100) return b[Math.floor(n / 10)] + (n % 10 !== 0 ? ' ' + a[n % 10] : ' ');
        if (n < 1000) return a[Math.floor(n / 100)] + 'Hundred ' + (n % 100 !== 0 ? 'and ' + inWords(n % 100) : '');
        if (n < 100000) return inWords(Math.floor(n / 1000)) + 'Thousand ' + (n % 1000 !== 0 ? inWords(n % 1000) : '');
        if (n < 10000000) return inWords(Math.floor(n / 100000)) + 'Lakh ' + (n % 100000 !== 0 ? inWords(n % 100000) : '');
        return inWords(Math.floor(n / 10000000)) + 'Crore ' + (n % 10000000 !== 0 ? inWords(n % 10000000) : '');
    }

    return inWords(num).trim() + ' Only';
}

export function formatIndianCurrency(num) {
    if (!num) return '';
    const n = parseInt(num, 10);
    if (isNaN(n)) return num;
    return n.toLocaleString('en-IN');
}

export function calculateEndDate(startDateStr, tenureMonths = 11) {
    if (!startDateStr) return '';
    const d = new Date(startDateStr);
    if (isNaN(d.getTime())) return '';
    d.setMonth(d.getMonth() + tenureMonths);
    d.setDate(d.getDate() - 1);
    return d.toISOString().split('T')[0];
}

export function calculateLockInEndDate(startDateStr, lockinMonths = 6) {
    if (!startDateStr) return '';
    const d = new Date(startDateStr);
    if (isNaN(d.getTime())) return '';
    d.setMonth(d.getMonth() + parseInt(lockinMonths, 10));
    d.setDate(d.getDate() - 1);
    return d.toISOString().split('T')[0];
}
