(function () {
    const configNode = document.getElementById("playerConfig");
    if (!configNode) {
        return;
    }

    const config = {
        moduleId: Number(configNode.dataset.moduleId),
        updateProgressUrl: configNode.dataset.updateProgressUrl,
        markCompleteUrl: configNode.dataset.markCompleteUrl,
        quizSubmitUrl: configNode.dataset.quizSubmitUrl,
        nextModuleUrl: configNode.dataset.nextModuleUrl,
        csrfToken: configNode.dataset.csrfToken,
        isLocked: configNode.dataset.isLocked === "true",
        isHls: configNode.dataset.isHls === "true",
        hlsSrc: configNode.dataset.hlsSrc,
        moduleProgress: Number(configNode.dataset.moduleProgress || 0),
        courseProgress: Number(configNode.dataset.courseProgress || 0),
        completedModules: Number(configNode.dataset.completedModules || 0),
        totalModules: Number(configNode.dataset.totalModules || 0),
        quizRequired: configNode.dataset.quizRequired === "true",
    };

    const video = document.getElementById("localVideo");
    const theorySection = document.getElementById("theorySection");
    const videoCard = document.getElementById("videoCard");
    const theoryBtn = document.getElementById("theoryBtn");
    const quizBtn = document.getElementById("quizBtn");
    const completeBtn = document.getElementById("completeBtn");
    const lockOverlay = document.getElementById("lockOverlay");
    const quizOverlay = document.getElementById("quizOverlay");
    const quizQuestion = document.getElementById("quizQuestion");
    const quizOptions = document.getElementById("quizOptions");
    const quizEmptyState = document.getElementById("quizEmptyState");
    const closeQuizBtn = document.getElementById("closeQuizBtn");
    const statusBox = document.getElementById("playerStatus");
    const moduleProgressBar = document.getElementById("progress-bar");
    const moduleProgressPercent = document.getElementById("progressPercent");
    const courseProgressBar = document.getElementById("course-progress-bar");
    const courseProgressPercent = document.getElementById("courseProgressPercent");

    let lastProgressSentAt = 0;
    let completeRequestInFlight = false;
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
        config.moduleProgress = Math.max(config.moduleProgress, safePercent);
    }

    function setCourseProgressBar(percent) {
        const safePercent = Math.max(0, Math.min(100, Math.round(percent)));
        if (courseProgressBar) {
            courseProgressBar.style.width = safePercent + "%";
        }
        if (courseProgressPercent) {
            courseProgressPercent.textContent = safePercent + "%";
        }
        config.courseProgress = safePercent;
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
            const message = data.message || "Request failed.";
            throw new Error(message);
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

    async function markComplete() {
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
            }, 250);
        } catch (error) {
            showStatus(error.message || "Unable to mark this module complete.", "error");
            completeRequestInFlight = false;
            if (completeBtn) {
                completeBtn.disabled = false;
            }
        }
    }

    function buildQuestions() {
        if (Array.isArray(quizData.questions) && quizData.questions.length) {
            return quizData.questions;
        }
        if (quizData.question) {
            return [{
                question: quizData.question,
                options: quizData.options || [],
                answer: quizData.answer,
            }];
        }
        return [];
    }

    async function submitQuizAnswer(answer) {
        try {
            const data = await postJson(config.quizSubmitUrl, {
                module_id: config.moduleId,
                answers: { 0: answer },
                theory_completed: true,
            });

            if (data.passed) {
                showStatus("Quiz submitted successfully.", "success");
            } else {
                showStatus(data.message || "Quiz submitted, but it did not reach the passing score.", "error");
            }
            if (quizOverlay) {
                quizOverlay.style.display = "none";
            }
        } catch (error) {
            showStatus(error.message || "Quiz submission failed.", "error");
        }
    }

    function openQuiz() {
        const questions = buildQuestions();
        if (!quizOverlay || !quizQuestion || !quizOptions || !quizEmptyState) {
            return;
        }

        quizOptions.innerHTML = "";
        if (!questions.length) {
            quizQuestion.textContent = "Quiz";
            quizEmptyState.style.display = "block";
            quizOverlay.style.display = "flex";
            return;
        }

        const firstQuestion = questions[0];
        quizQuestion.textContent = firstQuestion.question || "Quiz";
        quizEmptyState.style.display = "none";

        (firstQuestion.options || []).forEach(function (option) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn-action quiz-option";
            button.textContent = option;
            button.addEventListener("click", function () {
                submitQuizAnswer(option);
            });
            quizOptions.appendChild(button);
        });

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
            return;
        }

        if (config.isHls && window.Hls && window.Hls.isSupported() && config.hlsSrc) {
            const hls = new window.Hls();
            hls.loadSource(config.hlsSrc);
            hls.attachMedia(video);
        }

        setProgressBar(config.moduleProgress);
        setCourseProgressBar(config.courseProgress);

        video.addEventListener("timeupdate", function () {
            if (!Number.isFinite(video.duration) || video.duration <= 0) {
                return;
            }

            const now = Date.now();
            if (now - lastProgressSentAt < 2000) {
                return;
            }
            lastProgressSentAt = now;
            saveProgress(video.currentTime, video.duration);
        });

        video.addEventListener("ended", async function () {
            if (Number.isFinite(video.duration) && video.duration > 0) {
                await saveProgress(video.duration, video.duration);
            }
            showTheory();
            showStatus("Video progress saved. Review the theory and complete the module.", "success");
        });
    }

    if (lockOverlay && config.isLocked) {
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

    if (theoryBtn) {
        theoryBtn.addEventListener("click", showTheory);
    }

    if (quizBtn) {
        quizBtn.addEventListener("click", openQuiz);
    }

    if (closeQuizBtn && quizOverlay) {
        closeQuizBtn.addEventListener("click", function () {
            quizOverlay.style.display = "none";
        });
    }

    if (completeBtn) {
        completeBtn.addEventListener("click", markComplete);
    }
})();
