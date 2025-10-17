const mongoose = require('mongoose');

const commentSchema = new mongoose.Schema({
    // Reference to the Post the comment belongs to
    post: {
        type: mongoose.Schema.Types.ObjectId,
        ref: 'Post',
        required: true,
        index: true // Index for fast retrieval of comments for a specific post
    },

    // Reference to the User who wrote the comment
    author: {
        type: mongoose.Schema.Types.ObjectId,
        ref: 'User',
        required: true,
    },

    // The actual content of the comment
    content: {
        type: String,
        required: true,
        minlength: 1,
        maxlength: 1024, // Keeps comments concise
        trim: true
    },
    

}, { timestamps: true }); 

module.exports = mongoose.model('Comment', commentSchema);
