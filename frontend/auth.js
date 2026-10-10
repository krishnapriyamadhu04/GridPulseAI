// =========================================
// PASSWORD VISIBILITY
// =========================================

const togglePassword =
    document.getElementById("togglePassword");

const passwordInput =
    document.getElementById("password");


if (togglePassword) {

    togglePassword.addEventListener(
        "click",
        function () {

            if (
                passwordInput.type === "password"
            ) {

                passwordInput.type = "text";

                togglePassword.textContent =
                    "Hide";

            } else {

                passwordInput.type = "password";

                togglePassword.textContent =
                    "Show";

            }

        }
    );

}


// =========================================
// LOGIN FORM
// =========================================

const loginForm =
    document.getElementById("loginForm");


if (loginForm) {

    loginForm.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();


            const email =
                document.getElementById(
                    "email"
                ).value.trim();


            const password =
                document.getElementById(
                    "password"
                ).value;


            const message =
                document.getElementById(
                    "loginMessage"
                );


            const loginButton =
                document.getElementById(
                    "loginButton"
                );


            message.textContent = "";

            message.className =
                "auth-message";


            // Basic validation

            if (!email || !password) {

                message.textContent =
                    "Please enter your email and password.";

                message.classList.add("error");

                return;
            }


            // Loading state

            loginButton.disabled = true;

            loginButton.textContent =
                "Logging in...";


            try {

                const response =
                    await fetch(
                        "/api/auth/login",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            credentials: "include",

                            body: JSON.stringify({
                                email: email,
                                password: password
                            })
                        }
                    );


                const data =
                    await response.json();


                if (!response.ok) {

                    throw new Error(
                        data.detail ||
                        "Login failed."
                    );

                }


                message.textContent =
                    "Login successful.";

                message.classList.add(
                    "success"
                );


                // Go to dashboard

                setTimeout(
                    function () {

                        window.location.href =
                            "/dashboard";

                    },
                    300
                );


            } catch (error) {

                message.textContent =
                    error.message;

                message.classList.add(
                    "error"
                );

                loginButton.disabled = false;

                loginButton.textContent =
                    "Log In";

            }

        }
    );

}