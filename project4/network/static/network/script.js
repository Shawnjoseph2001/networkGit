/**
 * This script handles user interactions with 'like', 'edit', and 'submit' buttons on the page.
 * It waits for the DOM to load and initializes event listeners for these buttons.
 *
 */

document.addEventListener('DOMContentLoaded', () => {
    // When the DOM is fully loaded, setup the event listeners
    handleLikeButtons();
    handleInitialElementVisibility();
    handleEditButtons();
    handleCommentButtons();
    handleSubmitEditButtons();
});

/**
 * Adds click event listeners to like buttons.
 * Each button makes an asynchronous request to either like or unlike a post based on its current state.
 */
function handleLikeButtons() {
    document.querySelectorAll('.like-button').forEach(button => {
        button.addEventListener('click', async function () {
            const postId = this.dataset.postId;
            const isLiked = this.dataset.liked === 'true';
            const serverId = this.dataset.server;
            const url = isLiked ? `/unlike_post/${serverId}/${postId}` : `/like_post/${serverId}/${postId}`;
            const method = isLiked ? 'DELETE' : 'GET';
            const response = await fetch(url, {method});
            const data = await response.json();

            if (data.success) {
                document.querySelector(`#like-count-${postId}`).textContent = `Like Count: ${data.likeCount}`;
                this.textContent = isLiked ? 'Like post' : 'Unlike post';
                this.dataset.liked = isLiked ? 'false' : 'true';
            } else {
                console.error('An error occurred while liking/unliking the post.');
            }
        });
    });
}

/**
 * Initially hides the edit-content and submit-edit-button elements.
 */
function handleInitialElementVisibility() {
    document.querySelectorAll('.edit-content, .submit-edit-button, .comment-content, .submit-comment-button').forEach(elem => {
        elem.style.display = 'none';
    });
}

/**
 * Adds click event listeners to edit buttons.
 * When a user clicks an edit button, it hides the current post content and the edit button itself,
 * while revealing the text input for editing and the button to submit changes.
 */
function handleEditButtons() {
    document.querySelectorAll('.edit-button').forEach(button => {
        button.addEventListener('click', function () {
            const postId = this.dataset.postId;
            document.getElementById(`edit-button-${postId}`).style.display = "none";
            document.getElementById(`edit-content-${postId}`).style.display = "inline";
            document.getElementById(`submit-edit-button-${postId}`).style.display = "inline";
            document.getElementById(`post-content-${postId}`).style.display = "none";
        });
    });
}


function handleCommentButtons() {
    document.querySelectorAll('.comment-button').forEach(button => {
        button.addEventListener('click', function () {
            const postId = this.dataset.postId;
            document.getElementById(`comment-button-${postId}`).style.display = "none";
            document.getElementById(`comment-content-${postId}`).style.display = "inline";
            document.getElementById(`submit-comment-button-${postId}`).style.display = "inline";
        });
    });
}


/**
 * Adds click event listeners to submit-edit buttons.
 * When a user clicks a submit button, it makes an asynchronous request to update the post content,
 * then updates the content displayed on the page without needing to reload.
 */
function handleSubmitEditButtons() {
    document.querySelectorAll('.submit-edit-button').forEach(button => {
        button.addEventListener('click', async function () {
            const postId = this.dataset.postId;
            const newText = document.getElementById(`edit-content-${postId}`);
            const oldText = document.getElementById(`post-content-${postId}`);
            const bodyContent = JSON.stringify({content: newText.value});

            const response = await fetch(`/edit/${postId}`, {
                method: 'POST', headers: {
                    'Content-Type': 'application/json'
                }, body: bodyContent
            });

            const result = await response.json();
            oldText.textContent = result.content;
            newText.value = result.content;
            newText.style.display = 'none';
            oldText.style.display = 'block';
            document.getElementById(`edit-button-${postId}`).style.display = "block";
            document.getElementById(`submit-edit-button-${postId}`).style.display = "none";
        });
    });
}