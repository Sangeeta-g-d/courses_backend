document.addEventListener('DOMContentLoaded', function() {
    const videoPlayer = document.getElementById('main-video-player');
    const videoTitle = document.getElementById('video-title');
    const videoDescription = document.getElementById('video-description');
    const videoSectionTitle = document.getElementById('video-section-title');

    let currentLectureId = null;
    let progressUpdateInterval = null;
    
    // Safe CSRF token retrieval
    const getCSRFToken = () => {
        const csrfElement = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfElement) {
            return csrfElement.value;
        }
        
        // Alternative method to get CSRF token from cookies
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
            
        return cookieValue || '';
    };

    const csrftoken = getCSRFToken();

    // Server-initial values
    const initialLectureId = window.initialLectureId || null;
    const initialVideoUrl = window.initialVideoUrl || null;

    function findLectureElement(lectureId) {
        return document.querySelector('.lecture-item[data-lecture-id="' + lectureId + '"]');
    }

    function updateLectureProgressUI(lectureId, progressPercentage, completed = false) {
        const lectureElement = findLectureElement(lectureId);
        if (!lectureElement) return;

        if (completed) {
            lectureElement.setAttribute('data-is-completed', 'true');
            const icon = lectureElement.querySelector('.fa-unlock, .fa-lock, .fa-check-circle');
            if (icon) icon.className = 'fas fa-check-circle text-success';
            
            // Remove progress bar if completed
            const progressBar = lectureElement.querySelector('.progress');
            if (progressBar) progressBar.remove();
            const progressText = lectureElement.querySelector('.text-muted');
            if (progressText && progressText.textContent.includes('% watched')) {
                progressText.remove();
            }
        } else if (progressPercentage > 0) {
            // Update or create progress bar
            let progressBar = lectureElement.querySelector('.progress');
            let progressText = lectureElement.querySelector('.text-muted');
            
            if (!progressBar) {
                const flexContainer = lectureElement.querySelector('.flex-grow-1');
                if (flexContainer) {
                    progressBar = document.createElement('div');
                    progressBar.className = 'progress mt-1';
                    progressBar.style.height = '4px';
                    progressBar.innerHTML = `
                        <div class="progress-bar bg-primary" role="progressbar" 
                             style="width: ${progressPercentage}%;" 
                             aria-valuenow="${progressPercentage}" 
                             aria-valuemin="0" 
                             aria-valuemax="100">
                        </div>
                    `;
                    
                    progressText = document.createElement('small');
                    progressText.className = 'text-muted';
                    progressText.textContent = `${Math.round(progressPercentage)}% watched`;
                    
                    flexContainer.appendChild(progressBar);
                    flexContainer.appendChild(progressText);
                }
            } else {
                // Update existing progress bar
                const progressBarInner = progressBar.querySelector('.progress-bar');
                if (progressBarInner) {
                    progressBarInner.style.width = `${progressPercentage}%`;
                    progressBarInner.setAttribute('aria-valuenow', progressPercentage);
                }
                if (progressText) {
                    progressText.textContent = `${Math.round(progressPercentage)}% watched`;
                }
            }
        }
    }

    function attachLectureClick(li) {
        if (!li || li._clickAttached) return;
        li._clickAttached = true;
        
        li.addEventListener('click', function() {
            if (li.getAttribute('data-is-accessible') !== 'true') {
                console.log('Clicked locked lecture', li.getAttribute('data-lecture-id'));
                return;
            }
            
            const videoUrl = li.getAttribute('data-video-url');
            const lectureTitle = li.getAttribute('data-lecture-title');
            const isPreview = li.getAttribute('data-is-preview') === 'true';
            const isEnrolled = li.getAttribute('data-is-enrolled') === 'true';
            const isAuthenticated = li.getAttribute('data-is-authenticated') === 'true';
            const lectureId = li.getAttribute('data-lecture-id');

            if (!isAuthenticated) {
                alert('Please login to access course videos.');
                window.location.href = "/user/login/?next=" + window.location.pathname;
                return;
            }
            if (!isEnrolled && !isPreview) {
                alert('Please enroll in the course to access this video.');
                return;
            }

            if (videoUrl) {
                // Set video source
                videoPlayer.innerHTML = '';
                const source = document.createElement('source');
                source.src = videoUrl;
                source.type = 'video/mp4';
                videoPlayer.appendChild(source);

                // Update UI
                videoTitle.textContent = lectureTitle;
                videoDescription.textContent = isPreview ? ('Preview Video - ' + lectureTitle) : lectureTitle;
                videoSectionTitle.textContent = 'Now Playing: ' + lectureTitle;

                videoPlayer.load();
                
                // Set current time from progress if available
                const progressPercentage = parseFloat(li.getAttribute('data-progress-percentage') || 0);
                if (progressPercentage > 0) {
                    videoPlayer.addEventListener('loadedmetadata', function() {
                        const seekTime = (progressPercentage / 100) * videoPlayer.duration;
                        videoPlayer.currentTime = Math.min(seekTime, videoPlayer.duration - 10); // Don't start at the very end
                    }, { once: true });
                }

                videoPlayer.play().catch(e => console.log('Autoplay prevented:', e));

                document.querySelectorAll('.lecture-item').forEach(l => l.classList.remove('lecture-playing'));
                li.classList.add('lecture-playing');

                currentLectureId = lectureId;
                console.log('currentLectureId set ->', currentLectureId);

                // Scroll to video
                const videoCard = document.querySelector('.card-body.p-4');
                if (videoCard) videoCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
            } else {
                alert('Video not available for this lecture.');
            }
        });
    }

    // Attach handlers to lecture items
    document.querySelectorAll('.lecture-item').forEach(li => {
        if (li.getAttribute('data-is-accessible') === 'true') {
            li.classList.add('clickable-lecture');
            attachLectureClick(li);
        }
    });

    // Initialize player from server data
    (function initializePlayerFromServer() {
        try {
            if (initialLectureId) {
                const el = findLectureElement(initialLectureId);
                if (el && el.getAttribute('data-is-accessible') === 'true') {
                    const url = el.getAttribute('data-video-url');
                    if (url) {
                        videoPlayer.innerHTML = '';
                        const source = document.createElement('source');
                        source.src = url;
                        source.type = 'video/mp4';
                        videoPlayer.appendChild(source);
                        videoPlayer.load();
                        
                        currentLectureId = initialLectureId;
                        el.classList.add('lecture-playing');
                        el.classList.add('clickable-lecture');
                        attachLectureClick(el);
                        
                        const lectureTitle = el.getAttribute('data-lecture-title') || '';
                        videoTitle.textContent = lectureTitle;
                        videoDescription.textContent = lectureTitle;
                        videoSectionTitle.textContent = 'Continue: ' + lectureTitle;
                        
                        console.log('Initialized player from server: lecture', currentLectureId);
                    }
                }
            }
        } catch (e) {
            console.warn('Initialization from server failed', e);
        }
    })();

    // Video events
    if (videoPlayer) {
        videoPlayer.addEventListener('play', function() {
            if (progressUpdateInterval) clearInterval(progressUpdateInterval);
            progressUpdateInterval = setInterval(updateVideoProgress, 5000); // Update every 5 seconds
        });

        videoPlayer.addEventListener('pause', function() {
            if (progressUpdateInterval) clearInterval(progressUpdateInterval);
            updateVideoProgress();
        });

        videoPlayer.addEventListener('timeupdate', function() {
            // Update local progress display without saving to server
            if (currentLectureId && videoPlayer.currentTime > 0 && videoPlayer.duration > 0) {
                const progressPercentage = (videoPlayer.currentTime / videoPlayer.duration) * 100;
                updateLectureProgressUI(currentLectureId, progressPercentage);
            }
        });

        videoPlayer.addEventListener('ended', function() {
            if (progressUpdateInterval) clearInterval(progressUpdateInterval);
            console.log('Video ended for', currentLectureId);
            if (currentLectureId) {
                markLectureCompleted(currentLectureId);
            }
        });

        window.addEventListener('beforeunload', function() {
            if (progressUpdateInterval) clearInterval(progressUpdateInterval);
            updateVideoProgressSync();
        });
    }

    function updateVideoProgress() {
        if (!currentLectureId || !csrftoken) return;
        if (!videoPlayer || videoPlayer.currentTime <= 0) return;
        
        const watched = Math.floor(videoPlayer.currentTime);
        const total = Math.floor(videoPlayer.duration) || 0;
        const progressPercentage = total > 0 ? (watched / total) * 100 : 0;

        console.log('Sending progress', { 
            lecture: currentLectureId, 
            watched, 
            total, 
            progress: progressPercentage 
        });

        const formData = new FormData();
        formData.append('watched_duration', watched);
        formData.append('total_duration', total);

        fetch(`/user/update-lecture-progress/${currentLectureId}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrftoken },
            body: formData,
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                console.log('Progress updated successfully');
                // Update UI with actual progress from server
                updateLectureProgressUI(currentLectureId, progressPercentage);
            }
        })
        .catch(err => {
            console.error('Error sending progress:', err);
            // Continue with UI update even if server request fails
            updateLectureProgressUI(currentLectureId, progressPercentage);
        });
    }

    function updateVideoProgressSync() {
        if (!currentLectureId || !csrftoken) return;
        if (!videoPlayer || videoPlayer.currentTime <= 0) return;
        
        try {
            const watched = Math.floor(videoPlayer.currentTime);
            const total = Math.floor(videoPlayer.duration) || 0;
            
            if (navigator.sendBeacon) {
                const url = `/user/update-lecture-progress/${currentLectureId}/`;
                const formData = new FormData();
                formData.append('watched_duration', watched);
                formData.append('total_duration', total);
                formData.append('csrfmiddlewaretoken', csrftoken);
                
                // Convert FormData to URLSearchParams for sendBeacon
                const params = new URLSearchParams();
                for (const [key, value] of formData.entries()) {
                    params.append(key, value);
                }
                
                navigator.sendBeacon(url, params);
                console.log('sendBeacon progress', { lecture: currentLectureId, watched, total });
            }
        } catch (e) { 
            console.warn('sendBeacon failed', e); 
        }
    }

    function computeClientNextLectureId(currentId) {
        const currentLi = findLectureElement(currentId);
        if (!currentLi) return null;
        
        const ul = currentLi.closest('ul');
        if (!ul) return null;
        
        const allLecturesInSection = Array.from(ul.querySelectorAll('.lecture-item'));
        const currentIndex = allLecturesInSection.findIndex(li => li.getAttribute('data-lecture-id') === currentId);
        
        if (currentIndex === -1) return null;
        
        // Check next lecture in same section
        if (currentIndex + 1 < allLecturesInSection.length) {
            const nextLecture = allLecturesInSection[currentIndex + 1];
            return nextLecture.getAttribute('data-lecture-id');
        }
        
        // If no more lectures in current section, check next section
        const accordionItem = ul.closest('.accordion-item');
        if (!accordionItem) return null;
        
        let nextSection = accordionItem.nextElementSibling;
        while (nextSection) {
            if (nextSection.classList.contains('accordion-item')) {
                const firstLecture = nextSection.querySelector('.lecture-item');
                if (firstLecture) return firstLecture.getAttribute('data-lecture-id');
            }
            nextSection = nextSection.nextElementSibling;
        }
        
        return null;
    }

    function unlockNextLecture(nextId) {
        if (!nextId) return;
        
        const nextLi = findLectureElement(nextId);
        if (nextLi) {
            nextLi.setAttribute('data-is-accessible', 'true');
            nextLi.classList.add('clickable-lecture');

            // Update lock icon to unlock icon
            const rightDiv = nextLi.querySelector('div.d-flex.align-items-center:last-child');
            if (rightDiv) {
                const existingIcons = rightDiv.querySelectorAll('.fa-lock, .fa-unlock, .fa-check-circle');
                existingIcons.forEach(icon => icon.remove());
                
                const unlockIcon = document.createElement('i');
                unlockIcon.className = 'fas fa-unlock text-success';
                unlockIcon.title = 'Click to play';
                rightDiv.appendChild(unlockIcon);
            }

            attachLectureClick(nextLi);
            console.log('Successfully unlocked next lecture:', nextId);
            
            // Show notification
            showNotification('Next lecture unlocked!', 'success');
        } else {
            console.log('Next lecture element not found:', nextId);
        }
    }

    function showNotification(message, type = 'info') {
        // Simple notification - you can replace with a proper notification library
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(notification);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    }

    function markLectureCompleted(lectureId) {
        if (!lectureId || !csrftoken) { 
            console.warn('markLectureCompleted called without id or CSRF token'); 
            return; 
        }

        console.log('Starting markLectureCompleted for lecture:', lectureId);

        const watched = Math.floor(videoPlayer.currentTime) || 0;
        const total = Math.floor(videoPlayer.duration) || 0;

        fetch(`/user/mark-lecture-completed/${lectureId}/`, {
            method: 'POST',
            headers: { 
                'X-CSRFToken': csrftoken,
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `watched_duration=${watched}&total_duration=${total}`
        })
        .then(resp => {
            console.log('Response status:', resp.status);
            return resp.json().then(json => ({ status: resp.status, ok: resp.ok, json }));
        })
        .then(({ status, ok, json }) => {
            console.log('mark_lecture_completed response:', json);

            if (ok && json.success) {
                // Update UI to show completed
                updateLectureProgressUI(lectureId, 100, true);
                showNotification('Lecture completed!', 'success');

                let nextId = json.next_lecture_id || null;
                console.log('Server returned next_lecture_id:', nextId);

                if (!nextId) {
                    nextId = computeClientNextLectureId(lectureId);
                    console.log('Client computed next_lecture_id:', nextId);
                }

                if (nextId) {
                    unlockNextLecture(nextId);
                } else {
                    showNotification('Congratulations! You have completed this section.', 'info');
                }
            } else {
                console.error('mark_lecture_completed failed with:', json);
                showNotification('Failed to mark lecture as completed', 'error');
            }
        })
        .catch(err => {
            console.error('Network error marking lecture completed:', err);
            showNotification('Network error. Please try again.', 'error');
        });
    }
});