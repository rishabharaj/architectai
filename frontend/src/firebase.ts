import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

export const demoMode = import.meta.env.VITE_APP_MODE === "demo";
const firebaseKey = import.meta.env.VITE_FIREBASE_API_KEY;

const app = !demoMode && firebaseKey
  ? initializeApp({
      apiKey: firebaseKey,
      authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
      projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
      appId: import.meta.env.VITE_FIREBASE_APP_ID,
      messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
    })
  : null;

export const auth = app ? getAuth(app) : null;
