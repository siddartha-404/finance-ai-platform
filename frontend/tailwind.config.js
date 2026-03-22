/** @type {import('tailwindcss').Config} */
export default {
    content: [
      "./index.html",
      "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
      extend: {
        colors: {
          finance: {
            dark: '#0f172a',
            primary: '#0ea5e9',
            accent: '#10b981',
            light: '#f8fafc'
          }
        }
      },
    },
    plugins: [],
  }