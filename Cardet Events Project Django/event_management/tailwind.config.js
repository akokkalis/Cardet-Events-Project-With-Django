/** Build with: tailwindcss -i ./core/static/css/tailwind-input.css -o ./core/static/vendor/css/tailwind.css --minify
 *  (run inside the django container so the crispy_tailwind site-packages path below resolves)
 */
module.exports = {
  content: [
    "./core/templates/**/*.html",
    "./core/static/js/**/*.js",
    "/usr/local/lib/python3.11/site-packages/crispy_tailwind/templates/**/*.html",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
