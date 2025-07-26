window.addEventListener("scroll", function () {
const navbar = document.querySelector(".navbar");
if (window.scrollY > 60) {
    navbar.classList.add("navbar-shrink");
} else {
    navbar.classList.remove("navbar-shrink");
}
});