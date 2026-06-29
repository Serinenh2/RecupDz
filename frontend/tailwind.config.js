export default {
  content: ['./index.html','./src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50:'#EAF3DE',100:'#D8E8C2',200:'#C0DD97',300:'#97C459',
          400:'#8FAE52',500:'#639922',600:'#5C8C2E',700:'#3B6D11',
          800:'#2D5A0F',900:'#27500A',950:'#173404',
        },
      },
      fontFamily: { sans: ['"Plus Jakarta Sans"','system-ui','sans-serif'] },
      boxShadow: {
        card:      '0 1px 3px 0 rgb(0 0 0/0.04), 0 4px 16px -2px rgb(0 0 0/0.06)',
        'card-lg': '0 4px 12px 0 rgb(0 0 0/0.08), 0 16px 40px -4px rgb(0 0 0/0.12)',
      },
    },
  },
  plugins: [],
}
