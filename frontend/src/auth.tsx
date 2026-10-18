import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  createUserWithEmailAndPassword, GoogleAuthProvider, onAuthStateChanged,
  sendPasswordResetEmail, signInWithEmailAndPassword, signInWithPopup, signOut,
  updateProfile, type User,
} from "firebase/auth";
import { auth, demoMode } from "./firebase";

type Account = { uid: string; displayName: string | null; email: string | null };
type AuthContextValue = {
  user: Account | null;
  loading: boolean;
  signInEmail(email: string, password: string): Promise<void>;
  signUpEmail(name: string, email: string, password: string): Promise<void>;
  signInGoogle(): Promise<void>;
  resetPassword(email: string): Promise<void>;
  logout(): Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Account | null>(demoMode ? { uid: "demo-local", displayName: "Demo User", email: null } : null);
  const [loading, setLoading] = useState(!demoMode && !!auth);

  useEffect(() => {
    if (!auth) { setLoading(false); return; }
    return onAuthStateChanged(auth, (current: User | null) => {
      setUser(current ? { uid: current.uid, displayName: current.displayName, email: current.email } : null);
      setLoading(false);
    });
  }, []);

  const requireAuth = () => {
    if (!auth) throw new Error("Firebase is not configured. Set the VITE_FIREBASE_* values.");
    return auth;
  };

  return <AuthContext.Provider value={{
    user, loading,
    signInEmail: async (email, password) => { await signInWithEmailAndPassword(requireAuth(), email, password); },
    signUpEmail: async (name, email, password) => {
      const result = await createUserWithEmailAndPassword(requireAuth(), email, password);
      if (name.trim()) { await updateProfile(result.user, { displayName: name.trim() }); setUser({ uid: result.user.uid, displayName: name.trim(), email: result.user.email }); }
    },
    signInGoogle: async () => { await signInWithPopup(requireAuth(), new GoogleAuthProvider()); },
    resetPassword: async (email) => { await sendPasswordResetEmail(requireAuth(), email); },
    logout: async () => { if (auth) await signOut(auth); },
  }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("AuthProvider is missing");
  return context;
}
