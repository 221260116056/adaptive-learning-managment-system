(function () {
    const configNode = document.getElementById("playerConfig");
    if (!configNode) {
        return;
    }

    const config = {
        moduleId: Number(configNode.dataset.moduleId),
        updateProgressUrl: configNode.dataset.updateProgressUrl,
        markCompleteUrl: configNode.dataset.markCompleteUrl,
        submitQuizUrl: configNode.dataset.submitQuizUrl,
        nextModuleUrl: configNode.dataset.nextModuleUrl,
        csrfToken: configNode.dataset.csrfToken,
        isLocked: configNode.dataset.isLocked === "true",
        isHls: configNode.dataset.isHls === "true",
        hlsSrc: configNode.dataset.hlsSrc,
        moduleProgress: Number(configNode.dataset.moduleProgress || 0),
        courseProgress: Number(configNode.dataset.courseProgress || 0),
        quizRequired: configNode.dataset.quizRequired === "true",
        quizId: Number(configNode.dataset.quizId || 0),
        attemptsRemaining: Number((configNode.dataset.attemptsRemaining || "0")),
        allowSeek: configNode.dataset.allowSeek === "true",
        minWatchPercent: Number(configNode.dataset.minWatchPercent || 80),
        enableCheckpoints: configNode.dataset.enableCheckpoints === "true",
        checkpointInterval: Number(configNode.dataset.checkpointInterval || 30),
        disableFastForward: configNode.dataset.disableFastForward === "true",
        dashManifest: configNode.dataset.dashManifest,
        fallbackSrc: configNode.dataset.fallbackSrc,
    };

    const video = document.getElementById("localVideo");
    const theorySection = document.getElementById("theorySection");
    const videoCard = document.getElementById("videoCard");
    const theoryBtn = document.getElementById("theoryBtn");
    const quizBtn = document.getElementById("quizBtn");
    const completeBtn = document.getElementById("completeBtn");
    const quizOverlay = document.getElementById("quizOverlay");
    const quizQuestion = document.getElementById("quizQuestion");
    const quizOptions = document.getElementById("quizOptions");
    const quizEmptyState = document.getElementById("quizEmptyState");
    const submitQuizBtn = document.getElementById("submitQuiz");
    const closeQuizBtn = document.getElementById("closeQuizBtn");
    const statusBox = document.getElementById("playerStatus");
    const moduleProgressBar = document.getElementById("progress-bar");
    const moduleProgressPercent = document.getElementById("progressPercent");
    const courseProgressBar = document.getElementById("course-progress-bar");
    const courseProgressPercent = document.getElementById("courseProgressPercent");
    const videoControls = document.getElementById("videoControls");
    const playPauseBtn = document.getElementById("playPauseBtn");
    const playIcon = document.getElementById("playIcon");
    const pauseIcon = document.getElementById("pauseIcon");
    const progressRange = document.getElementById("progressRange");
    const timeLabel = document.getElementById("timeLabel");
    const pipBtn = document.getElementById("pipBtn");
    const settingsBtn = document.getElementById("settingsBtn");
    const settingsPanel = document.getElementById("settingsPanel");
    const settingsMain = document.getElementById("settingsMain");
    const playbackSpeedRow = document.getElementById("playbackSpeedRow");
    const playbackSpeedValue = document.getElementById("playbackSpeedValue");
    const qualityRow = document.getElementById("qualityRow");
    const qualityValue = document.getElementById("qualityValue");
    const speedMenu = document.getElementById("speedMenu");
    const qualitySubmenu = document.getElementById("qualitySubmenu");

    let lastProgressSentAt = 0;
    let completeRequestInFlight = false;
    let quizSubmitting = false;
    const quizDataNode = document.getElementById("module-quiz-data");
    let quizData = {};

    if (quizDataNode && quizDataNode.textContent) {
        try {
            quizData = JSON.parse(quizDataNode.textContent) || {};
        } catch (error) {
            quizData = {};
        }
    }

    function showStatus(message, variant) {
        if (!statusBox) {
            return;
        }
        statusBox.textContent = message;
        statusBox.className = "";
        statusBox.classList.add(variant === "error" ? "error" : "success");
    }

    function clearStatus() {
        if (!statusBox) {
            return;
        }
        statusBox.textContent = "";
        statusBox.className = "";
        statusBox.style.display = "none";
    }

    function setProgressBar(percent) {
        const safePercent = Math.max(0, Math.min(100, Math.round(percent)));
        if (moduleProgressBar) {
            moduleProgressBar.style.width = safePercent + "%";
        }
        if (moduleProgressPercent) {
            moduleProgressPercent.textContent = safePercent + "%";
        }
    }

    function setCourseProgressBar(percent) {
        const safePercent = Math.max(0, Math.min(100, Math.round(percent)));
        if (courseProgressBar) {
            courseProgressBar.style.width = safePercent + "%";
        }
        if (courseProgressPercent) {
            courseProgressPercent.textContent = safePercent + "%";
        }
    }

    function formatBitrate(bps) {
        if (!Number.isFinite(bps) || bps <= 0) {
            return "";
        }
        const kbps = Math.round(bps / 1000);
        if (kbps >= 1000) {
            return (kbps / 1000).toFixed(1).replace(".0", "") + " Mbps";
        }
        return kbps + " kbps";
    }

    function showMainMenu() {
        if (settingsMain) {
            settingsMain.style.display = "block";
        }
        if (speedMenu) {
            speedMenu.classList.remove("show");
        }
        if (qualitySubmenu) {
            qualitySubmenu.classList.remove("show");
        }
    }

    async function postJson(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": config.csrfToken,
            },
            body: JSON.stringify(payload || {}),
        });

        let data = {};
        try {
            data = await response.json();
        } catch (error) {
            data = {};
        }

        if (!response.ok) {
            throw new Error(data.message || "Request failed.");
        }

        return data;
    }

    function showTheory() {
        if (videoCard) {
            videoCard.style.display = "none";
        }
        if (theorySection) {
            theorySection.style.display = "block";
            theorySection.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }

    async function saveProgress(currentTime, duration) {
        if (config.isLocked) {
            return null;
        }

        try {
            const data = await postJson(config.updateProgressUrl, {
                module_id: config.moduleId,
                current_time: currentTime,
                duration: duration,
            });
            if (typeof data.video_progress === "number") {
                setProgressBar(data.video_progress);
            }
            return data;
        } catch (error) {
            showStatus(error.message || "Unable to save progress right now.", "error");
            return null;
        }
    }

    async function markModuleComplete() {
        if (config.isLocked || completeRequestInFlight) {
            return;
        }

        completeRequestInFlight = true;
        if (completeBtn) {
            completeBtn.disabled = true;
        }
        clearStatus();

        try {
            const data = await postJson(config.markCompleteUrl, {});
            setProgressBar(100);
            if (typeof data.course_progress_percent === "number") {
                setCourseProgressBar(data.course_progress_percent);
            }
            showStatus("Module completed. Moving to the next lesson.", "success");
            window.setTimeout(function () {
                window.location.href = config.nextModuleUrl;
            }, 300);
        } catch (error) {
            showStatus(error.message || "Unable to mark this module complete.", "error");
            completeRequestInFlight = false;
            if (completeBtn) {
                completeBtn.disabled = false;
            }
        }
    }

    function renderQuiz() {
        if (!quizOverlay || !quizQuestion || !quizOptions || !quizEmptyState) {
            return false;
        }

        const questions = Array.isArray(quizData.questions) ? quizData.questions : [];
        quizOptions.innerHTML = "";

        if (!questions.length || !config.quizId) {
            quizQuestion.textContent = "Quiz";
            quizEmptyState.style.display = "block";
            if (submitQuizBtn) {
                submitQuizBtn.disabled = true;
            }
            return false;
        }

        quizQuestion.textContent = "Module Quiz";
        quizEmptyState.style.display = "none";
        if (submitQuizBtn) {
            submitQuizBtn.disabled = false;
        }

        questions.forEach(function (question, index) {
            const questionCard = document.createElement("div");
            questionCard.style.padding = "1rem";
            questionCard.style.border = "1px solid #e2e8f0";
            questionCard.style.borderRadius = "14px";
            questionCard.style.background = "#ffffff";

            const title = document.createElement("p");
            title.style.margin = "0 0 0.85rem";
            title.style.fontWeight = "700";
            title.textContent = (index + 1) + ". " + (question.text || "Question");
            questionCard.appendChild(title);

            (question.options || []).forEach(function (option) {
                const label = document.createElement("label");
                label.style.display = "flex";
                label.style.alignItems = "center";
                label.style.gap = "0.65rem";
                label.style.marginBottom = "0.75rem";
                label.style.cursor = "pointer";

                const input = document.createElement("input");
                input.type = "radio";
                input.name = "question_" + question.id;
                input.value = option.id;

                const text = document.createElement("span");
                text.textContent = option.text;

                label.appendChild(input);
                label.appendChild(text);
                questionCard.appendChild(label);
            });

            quizOptions.appendChild(questionCard);
        });

        return true;
    }

    async function submitQuiz() {
        if (quizSubmitting || !config.quizId) {
            return;
        }

        const answers = {};
        document.querySelectorAll('#quizOptions input[type="radio"]:checked').forEach(function (input) {
            answers[input.name.replace("question_", "")] = input.value;
        });

        if (!Object.keys(answers).length) {
            showStatus("Please select your answers before submitting the quiz.", "error");
            return;
        }

        quizSubmitting = true;
        if (submitQuizBtn) {
            submitQuizBtn.disabled = true;
        }

        try {
            const data = await postJson(config.submitQuizUrl, {
                quiz_id: config.quizId,
                answers: answers,
            });

            if (typeof data.attempts_remaining === "number") {
                config.attemptsRemaining = data.attempts_remaining;
            }

            if (data.passed) {
                showStatus("Quiz passed. Completing module now.", "success");
                if (quizOverlay) {
                    quizOverlay.style.display = "none";
                }
                await markModuleComplete();
            } else {
                showStatus(
                    "Quiz not passed. Attempts left: " + (data.attempts_remaining ?? config.attemptsRemaining) + ".",
                    "error"
                );
            }
        } catch (error) {
            showStatus(error.message || "Quiz submission failed.", "error");
        } finally {
            quizSubmitting = false;
            if (submitQuizBtn) {
                submitQuizBtn.disabled = false;
            }
        }
    }

    function openQuiz() {
        if (!quizOverlay) {
            return;
        }
        renderQuiz();
        quizOverlay.style.display = "flex";
    }

    function setupVideoTracking() {
        if (!video) {
            showTheory();
            return;
        }

        if (config.isLocked) {
            video.pause();
            video.controls = false;
            if (videoControls) {
                videoControls.style.display = "none";
            }
            if (settingsPanel) {
                settingsPanel.style.display = "none";
            }
            return;
        }

        if (settingsBtn && settingsPanel) {
            settingsBtn.addEventListener("click", function (event) {
                event.stopPropagation();
                settingsPanel.classList.toggle("show");
                showMainMenu();
            });

            document.addEventListener("click", function () {
                settingsPanel.classList.remove("show");
            });
        }

        if (playbackSpeedRow && speedMenu && settingsMain) {
            playbackSpeedRow.addEventListener("click", function (event) {
                event.stopPropagation();
                settingsMain.style.display = "none";
                speedMenu.classList.add("show");
            });
        }

        if (qualityRow && qualitySubmenu && settingsMain) {
            qualityRow.addEventListener("click", function (event) {
                event.stopPropagation();
                if (qualityRow.classList.contains("disabled")) {
                    return;
                }
                settingsMain.style.display = "none";
                qualitySubmenu.classList.add("show");
            });
        }

        if (speedMenu) {
            speedMenu.querySelectorAll(".submenu-back").forEach(function (btn) {
                btn.addEventListener("click", function (event) {
                    event.stopPropagation();
                    showMainMenu();
                });
            });
        }

        if (qualitySubmenu) {
            qualitySubmenu.querySelectorAll(".submenu-back").forEach(function (btn) {
                btn.addEventListener("click", function (event) {
                    event.stopPropagation();
                    showMainMenu();
                });
            });
        }

        if (playbackSpeedValue && video && speedMenu) {
            const speedOptions = [0.5, 0.75, 1, 1.25, 1.5, 2];
            speedMenu.querySelectorAll(".quality-option").forEach(function (opt) {
                opt.remove();
            });

            speedOptions.forEach(function (rate) {
                const option = document.createElement("button");
                option.type = "button";
                option.className = "quality-option";
                option.textContent = rate === 1 ? "Normal" : rate + "x";
                option.addEventListener("click", function (event) {
                    event.stopPropagation();
                    video.playbackRate = rate;
                    playbackSpeedValue.textContent = option.textContent;
                    speedMenu.querySelectorAll(".quality-option").forEach(function (btn) {
                        btn.classList.remove("active");
                    });
                    option.classList.add("active");
                    showMainMenu();
                });
                if (rate === 1) {
                    option.classList.add("active");
                }
                speedMenu.appendChild(option);
            });
        }

        if (config.dashManifest && window.dashjs) {
            console.log("MPD URL:", config.dashManifest);
            const player = window.dashjs.MediaPlayer().create();
            player.updateSettings({
                streaming: {
                    abr: {
                        autoSwitchBitrate: { video: true }
                    }
                }
            });
            player.initialize(video, config.dashManifest, true);

            player.on("streamInitialized", function () {
                console.log("Tracks:", player.getTracksFor("video"));
            });
            player.setAutoPlay(true);
            player.setMute(false);

            player.on(window.dashjs.MediaPlayer.events.ERROR, function (e) {
                console.error("DASH ERROR:", e);
                if (config.fallbackSrc) {
                    video.src = config.fallbackSrc;
                    showStatus("DASH failed. Falling back to standard video.", "error");
                }
                if (qualityRow) {
                    qualityRow.classList.add("disabled");
                    if (qualityValue) {
                        qualityValue.textContent = "Standard";
                    }
                }
            });

            function buildQualityMenu() {
                if (!qualitySubmenu) {
                    return;
                }

                const bitrates = player.getBitrateInfoListFor("video") || [];
                qualitySubmenu.querySelectorAll(".quality-option").forEach(function (opt) {
                    opt.remove();
                });

                if (!bitrates.length) {
                    const emptyBtn = document.createElement("button");
                    emptyBtn.type = "button";
                    emptyBtn.className = "quality-option active";
                    emptyBtn.textContent = "Quality unavailable";
                    emptyBtn.addEventListener("click", function (event) {
                        event.stopPropagation();
                        showMainMenu();
                    });
                    qualitySubmenu.appendChild(emptyBtn);
                    if (qualityValue) {
                        qualityValue.textContent = "Unavailable";
                    }
                    return;
                }

                const autoBtn = document.createElement("button");
                autoBtn.type = "button";
                autoBtn.className = "quality-option active";
                const autoLabel = bitrates[0] ? (bitrates[0].height + "p") : "Auto";
                autoBtn.textContent = "Auto (" + autoLabel + ")";
                autoBtn.addEventListener("click", function (event) {
                    event.stopPropagation();
                    player.setAutoSwitchQualityFor("video", true);
                    setActiveQuality(autoBtn);
                    if (qualityValue) {
                        qualityValue.textContent = "Auto (" + autoLabel + ")";
                    }
                    showMainMenu();
                });
                qualitySubmenu.appendChild(autoBtn);

                bitrates.forEach(function (rate, index) {
                    const option = document.createElement("button");
                    option.type = "button";
                    option.className = "quality-option";
                    const height = rate.height || "";
                    const bitrate = formatBitrate(rate.bitrate);
                    const label = height ? height + "p" : bitrate || "Quality";
                    option.textContent = bitrate ? label + " • " + bitrate : label;
                    option.addEventListener("click", function (event) {
                        event.stopPropagation();
                        player.setAutoSwitchQualityFor("video", false);
                        player.setQualityFor("video", index);
                        setActiveQuality(option);
                        if (qualityValue) {
                            qualityValue.textContent = label;
                        }
                        showMainMenu();
                    });
                    qualitySubmenu.appendChild(option);
                });

                function setActiveQuality(activeButton) {
                    qualitySubmenu.querySelectorAll(".quality-option").forEach(function (btn) {
                        btn.classList.remove("active");
                    });
                    activeButton.classList.add("active");
                }

                if (qualityValue) {
                    qualityValue.textContent = autoBtn.textContent;
                }
            }

            function retryBuildMenu(attemptsLeft) {
                buildQualityMenu();
                if (attemptsLeft <= 0) {
                    return;
                }
                const bitrates = player.getBitrateInfoListFor("video") || [];
                if (!bitrates.length) {
                    window.setTimeout(function () {
                        retryBuildMenu(attemptsLeft - 1);
                    }, 300);
                }
            }

            player.on(window.dashjs.MediaPlayer.events.STREAM_INITIALIZED, function () {
                buildQualityMenu();
            });

            player.on(window.dashjs.MediaPlayer.events.MANIFEST_LOADED, function () {
                retryBuildMenu(6);
            });
        } else if (config.isHls && window.Hls && window.Hls.isSupported() && config.hlsSrc) {
            const hls = new window.Hls();
            hls.loadSource(config.hlsSrc);
            hls.attachMedia(video);
            if (qualityRow) {
                qualityRow.classList.add("disabled");
                if (qualityValue) {
                    qualityValue.textContent = "Standard";
                }
            }
        } else if (config.isHls && video.canPlayType("application/vnd.apple.mpegurl") && config.hlsSrc) {
            video.src = config.hlsSrc;
            if (qualityRow) {
                qualityRow.classList.add("disabled");
                if (qualityValue) {
                    qualityValue.textContent = "Standard";
                }
            }
        } else if (config.fallbackSrc && video) {
            video.src = config.fallbackSrc;
            if (qualityRow) {
                qualityRow.classList.add("disabled");
                if (qualityValue) {
                    qualityValue.textContent = "Standard";
                }
            }
        } else if (qualityRow) {
            qualityRow.classList.add("disabled");
            if (qualityValue) {
                qualityValue.textContent = "Standard";
            }
        }
        setProgressBar(config.moduleProgress);
        setCourseProgressBar(config.courseProgress);

        if (playPauseBtn && video) {
            playPauseBtn.addEventListener("click", function () {
                if (video.paused) {
                    video.play();
                } else {
                    video.pause();
                }
            });
        }

        video.addEventListener("play", updatePlayState);
        video.addEventListener("pause", updatePlayState);

        if (progressRange && timeLabel) {
            video.addEventListener("timeupdate", function () {
                if (!Number.isFinite(video.duration) || video.duration <= 0) {
                    return;
                }
                const percent = (video.currentTime / video.duration) * 1000;
                if (!progressRange.matches(":active")) {
                    progressRange.value = Math.floor(percent);
                }
                timeLabel.textContent = formatTime(video.currentTime) + " / " + formatTime(video.duration);
            });

            progressRange.addEventListener("input", function () {
                if (!Number.isFinite(video.duration) || video.duration <= 0) {
                    return;
                }
                const seekTime = (Number(progressRange.value) / 1000) * video.duration;
                video.currentTime = seekTime;
            });
        }

        if (pipBtn && video) {
            pipBtn.addEventListener("click", async function () {
                try {
                    if (document.pictureInPictureElement) {
                        await document.exitPictureInPicture();
                    } else if (document.pictureInPictureEnabled) {
                        await video.requestPictureInPicture();
                    }
                } catch (error) {
                    showStatus("Picture-in-picture not available.", "error");
                }
            });
        }

        let lastTime = 0;
        let checkpointTime = 0;

        if (config.disableFastForward) {
            video.addEventListener("ratechange", function () {
                if (video.playbackRate > 1.0) {
                    video.playbackRate = 1.0;
                    showStatus("Fast-forwarding is disabled for this module.", "error");
                }
            });
        }

        video.addEventListener("timeupdate", function () {
            if (!Number.isFinite(video.duration) || video.duration <= 0) {
                return;
            }

            let current = video.currentTime;
            let duration = video.duration;

            // BLOCK SEEKING
            if (!config.allowSeek && current > lastTime + 2) {
                video.currentTime = lastTime;
                return;
            }

            lastTime = current;
            let percent = (current / duration) * 100;

            // CHECKPOINT TRIGGER
            if (config.enableCheckpoints && current >= checkpointTime + config.checkpointInterval) {
                video.pause();
                
                // Show a simple checkpoint popup (could be enhanced later)
                const proceed = window.confirm("Checkpoint Reached! Are you still watching?");
                if (proceed) {
                    video.play();
                }
                checkpointTime = current;
            }

            const now = Date.now();
            if (now - lastProgressSentAt >= 5000) {
                lastProgressSentAt = now;
                
                // SEND CEALS HEARTBEAT
                fetch("/video/heartbeat/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": config.csrfToken
                    },
                    body: JSON.stringify({
                        module_id: config.moduleId,
                        current_time: current,
                        percent: percent
                    })
                });
            }
        });

        video.addEventListener("ended", async function () {
            // Replay log
            fetch("/video/replay/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": config.csrfToken
                },
                body: JSON.stringify({
                    module_id: config.moduleId,
                })
            });

            if (Number.isFinite(video.duration) && video.duration > 0) {
                await saveProgress(video.duration, video.duration);
            }
            showTheory();
            showStatus("Video playback recorded. Review the theory and submit the quiz.", "success");
        });
    }

    if (config.isLocked) {
        if (theoryBtn) {
            theoryBtn.disabled = true;
        }
        if (quizBtn) {
            quizBtn.disabled = true;
        }
        if (completeBtn) {
            completeBtn.disabled = true;
        }
        setProgressBar(config.moduleProgress);
        setCourseProgressBar(config.courseProgress);
        return;
    }

    setProgressBar(config.moduleProgress);
    setCourseProgressBar(config.courseProgress);
    setupVideoTracking();

    if (submitQuizBtn) {
        submitQuizBtn.addEventListener("click", submitQuiz);
    }

    if (config.quizRequired) {
        renderQuiz();
    }

    if (completeBtn) {
        completeBtn.addEventListener("click", function () {
            markModuleComplete();
        });
    }
})();
    function formatTime(seconds) {
        if (!Number.isFinite(seconds) || seconds < 0) {
            return "0:00";
        }
        const totalSeconds = Math.floor(seconds);
        const mins = Math.floor(totalSeconds / 60);
        const secs = totalSeconds % 60;
        return mins + ":" + String(secs).padStart(2, "0");
    }

    function updatePlayState() {
        if (!playIcon || !pauseIcon || !video) {
            return;
        }
        if (video.paused) {
            playIcon.style.display = "block";
            pauseIcon.style.display = "none";
        } else {
            playIcon.style.display = "none";
            pauseIcon.style.display = "block";
        }
    }
