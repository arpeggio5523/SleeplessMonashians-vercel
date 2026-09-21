import { create } from "zustand";

export const useToastStore = create((set) => ({
  message: null,
  showToast: (message) => {
    set({ message });
    setTimeout(() => set({ message: null }), 2000);
  },
}));