 const mongoose = require('mongoose');
 
  
  const postSchema = new mongoose.Schema({
    author:{
        type: mongoose.Schema.Types.ObjectId,
        ref:'User',
        required:true
    },

    title:{
        type:String,
        required:true,
        index:true,
        minlength:1,
        maxlength:256,
    },
    content:{
        type:String,
        required:true,
        minlength:1,
        maxlength:40960,
        index:true,
    },
    comments:[{
        type: mongoose.Schema.Types.ObjectId,
        ref:'Comment',
    }],
    likes:[{
        type: mongoose.Schema.Types.ObjectId,
        ref:'User',
    }],
},{timestamps:true});

  

  module.exports = mongoose.model('Post', postSchema);