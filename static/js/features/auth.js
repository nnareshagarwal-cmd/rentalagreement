/**
 * auth.js — Multi-Tenant User Authentication & User-Scoped Drafts
 * ================================================================
 */

export let currentUser = null;

export async function checkAuthSession() {
    try {
        const res = await fetch('/api/auth/me');
        const data = await res.json();
        if (data.authenticated && data.user) {
            currentUser = data.user;
            updateUserUI(currentUser);
            return currentUser;
        }
    } catch (e) {
        console.warn('[Auth] Session check failed:', e);
    }
    updateUserUI(null);
    return null;
}

export async function loginUser(email, password) {
    const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (data.success && data.user) {
        currentUser = data.user;
        updateUserUI(currentUser);
        return data.user;
    }
    throw new Error(data.error || 'Login failed');
}

export async function logoutUser() {
    await fetch('/api/auth/logout', { method: 'POST' });
    currentUser = null;
    updateUserUI(null);
}

function updateUserUI(user) {
    const userBadge = document.getElementById('userAuthBadge');
    if (!userBadge) return;
    if (user) {
        userBadge.innerHTML = `
            <span style="font-size:12px; font-weight:600; color:#1e293b;">👤 ${user.full_name || user.email}</span>
            <button id="logoutBtn" style="background:#ef4444; color:white; border:none; border-radius:4px; padding:3px 8px; font-size:11px; cursor:pointer;">Logout</button>
        `;
        document.getElementById('logoutBtn')?.addEventListener('click', logoutUser);
    } else {
        userBadge.innerHTML = `
            <button id="loginModalBtn" style="background:#2563eb; color:white; border:none; border-radius:6px; padding:5px 12px; font-size:12px; font-weight:600; cursor:pointer;">🔑 Login / Signup</button>
        `;
        document.getElementById('loginModalBtn')?.addEventListener('click', showAuthModal);
    }
}

export function showAuthModal() {
    let modal = document.getElementById('authModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'authModal';
        modal.className = 'popup-overlay';
        modal.style.cssText = 'display:flex; position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:9999; align-items:center; justify-content:center;';
        modal.innerHTML = `
            <div style="background:white; border-radius:12px; padding:24px; width:90%; max-width:380px; box-shadow:0 10px 25px rgba(0,0,0,0.2);">
                <h3 style="margin-top:0; margin-bottom:12px;">👤 Account Login</h3>
                <p style="font-size:12px; color:#64748b; margin-bottom:16px;">Log in to access and isolate your personal property agreement drafts.</p>
                <div style="margin-bottom:12px;">
                    <label style="font-size:11px; font-weight:600; display:block; margin-bottom:4px;">Email Address</label>
                    <input type="email" id="authEmailInput" placeholder="name@example.com" style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:6px; box-sizing:border-box;">
                </div>
                <div style="margin-bottom:20px;">
                    <label style="font-size:11px; font-weight:600; display:block; margin-bottom:4px;">Password</label>
                    <input type="password" id="authPasswordInput" placeholder="••••••••" style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:6px; box-sizing:border-box;">
                </div>
                <div style="display:flex; justify-content:flex-end; gap:8px;">
                    <button type="button" id="closeAuthModalBtn" style="padding:6px 12px; border:1px solid #cbd5e1; background:white; border-radius:6px; cursor:pointer;">Cancel</button>
                    <button type="button" id="submitAuthBtn" style="padding:6px 16px; background:#2563eb; color:white; border:none; border-radius:6px; font-weight:600; cursor:pointer;">Log In</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        document.getElementById('closeAuthModalBtn').addEventListener('click', () => modal.style.display = 'none');
        document.getElementById('submitAuthBtn').addEventListener('click', async () => {
            const email = document.getElementById('authEmailInput').value;
            const pass = document.getElementById('authPasswordInput').value;
            try {
                await loginUser(email, pass);
                modal.style.display = 'none';
            } catch (e) {
                alert(e.message);
            }
        });
    } else {
        modal.style.display = 'flex';
    }
}
