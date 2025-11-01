
        // Password strength indicator
        document.getElementById('password').addEventListener('input', function() {
            const password = this.value;
            const strengthBar = document.querySelector('.password-strength .progress-bar');
            const strengthText = document.querySelector('.password-strength-text');
            
            let strength = 0;
            let color = 'bg-danger';
            let message = 'Password strength';
            
            if (password.length >= 8) strength += 25;
            if (password.match(/[a-z]/) && password.match(/[A-Z]/)) strength += 25;
            if (password.match(/\d/)) strength += 25;
            if (password.match(/[^a-zA-Z\d]/)) strength += 25;
            
            if (strength >= 75) {
                color = 'bg-success';
                message = 'Strong password';
            } else if (strength >= 50) {
                color = 'bg-warning';
                message = 'Medium password';
            } else if (strength >= 25) {
                color = 'bg-danger';
                message = 'Weak password';
            } else {
                message = 'Password strength';
            }
            
            strengthBar.style.width = strength + '%';
            strengthBar.className = 'progress-bar ' + color;
            strengthText.textContent = message;
            
            // Also trigger password match check when password changes
            checkPasswordMatch();
        });

        // Password confirmation check
        function checkPasswordMatch() {
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirm_password').value;
            const messageDiv = document.querySelector('.password-match-message');
            const messageText = document.querySelector('.password-match-text');
            const confirmInput = document.getElementById('confirm_password');
            
            if (confirmPassword === '') {
                messageDiv.style.display = 'none';
                confirmInput.classList.remove('is-invalid', 'is-valid');
            } else if (password !== confirmPassword) {
                messageDiv.style.display = 'block';
                messageText.textContent = 'Passwords do not match';
                confirmInput.classList.add('is-invalid');
                confirmInput.classList.remove('is-valid');
            } else {
                messageDiv.style.display = 'none';
                confirmInput.classList.remove('is-invalid');
                confirmInput.classList.add('is-valid');
            }
        }

        document.getElementById('confirm_password').addEventListener('input', checkPasswordMatch);

        // Form validation on submit
        document.querySelector('form').addEventListener('submit', function(e) {
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirm_password').value;
            
            if (password !== confirmPassword) {
                e.preventDefault();
                checkPasswordMatch();
                document.getElementById('confirm_password').focus();
            }
        });
