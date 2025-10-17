const mongoose = require("mongoose")

const userSchema = new mongoose.Schema({
    userName:{
        type:String,
        required:true,
        lowercase:true,
        trim:true,
        minlength: 3,
        maxlength: 100,
        index: true, // at mongoDB index is we want to search quickly in an optimized way set index:true
    },
    name:{
        type:String,
        required:true,
    },
    profileImage:{
        type:String,
        default:"https://img.freepik.com/premium-vector/user-profile-icon-flat-style-member-avatar-vector-illustration-isolated-background-human-permission-sign-business-concept_157943-15752.jpg?semt=ais_hybrid&w=740&q=80"
    },
    email:{
        type:String,
        required:true,
        unique:true,
        lowercase:true, 
        trim:true,
        unique:true,
        index:true,
    },
    password:{
        type:String,
        required:true,
        minlength:1,
        maxlength:64,
        trim:true,
        index:true,
    },

    bio:{
        type:String,
        min:1,
        max:350
    },
    jobTitle:{
        type:String,
        index:true,
    },
    
    location:{
        type:String,
        index:true,
    },
    age:{
        type:Number,
        required:true,
        min:1,
        max:150,
        trim:true
    },
    follower: [{
       type: mongoose.Schema.ObjectId,
       ref: "User"
    }],
   following: [{
       type: mongoose.Schema.ObjectId,
       ref: "User"
    }],

    posts:[{
        type:mongoose.Schema.ObjectId,
        ref:'Post'
    }]
    
},{timestamps:true})


module.exports=mongoose.model("User",userSchema)

