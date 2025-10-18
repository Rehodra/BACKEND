const express = require('express');
const app = express();
const path = require('path');
const mongoose = require('mongoose');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
const cookieParser = require('cookie-parser');
const session = require('express-session');
const flash = require('connect-flash');
const upload = require('./config/multer.config');

const userModel = require('./models/user.model');
const postModel = require('./models/post.model');
const commentsModel = require('./models/comments.model');

require('dotenv').config();

const PORT = process.env.PORT || 3000;
const MONGO_URI = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/blog';
const JWT_SECRET = process.env.JWT_SECRET || 'abcd';
const DB_NAME = process.env.DATABASE_NAME || 'blog';

// Connect to MongoDB

mongoose
  .connect(`${MONGO_URI}/${DB_NAME}`)
  .then(() => console.log('MongoDB Connected Successfully'))
  .catch((err) => console.error('MongoDB Connection Failed:', err));

app.set('view engine', 'ejs');
app.use(express.json());
app.use(cookieParser());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

// Session + Flash (for user-facing messages)
app.use(session({
  secret: process.env.SESSION_SECRET || 'keyboard cat',
  resave: false,
  saveUninitialized: false,
  cookie: { secure: false }
}));
app.use(flash());

// Expose flash to templates
app.use((req, res, next) => {
  res.locals.flashError = req.flash('error');
  res.locals.flashSuccess = req.flash('success');
  next();
});


app.get('/', async (req, res) => {
  const token = req.cookies.token;

  // Fetch posts in the route
  const featuredPosts = await postModel.find({})
    .populate('author')
    .sort({ createdAt: -1 })
    .limit(4);

  res.render('homepage-static', { token, posts: featuredPosts });
});

app.get('/dashboard', isLoggedIn, async (req, res) => {
    const user = await userModel.findOne({ email: req.user.email })
        .populate('posts')
        .populate('following')
        .populate('follower');

    if (!user) {
        return res.status(404).send("User not found");
    }

    const userId = user._id;

    const commentLikesResult = await commentsModel.aggregate([
  { $match: { author: userId } },
  {
    $group: {
      _id: null,
      count: {
        $sum: { $size: { $ifNull: ["$likes", []] } } 
      }
    }
  }
]);

const postLikesResult = await postModel.aggregate([
  { $match: { author: userId } },
  {
    $group: {
      _id: null,
      count: {
        $sum: { $size: { $ifNull: ["$likes", []] } }
      }
    }
  }
]);

    const totalPostLikes = postLikesResult.length > 0 ? postLikesResult[0].count : 0;

    const totalCommentLikes = commentLikesResult.length > 0 ? commentLikesResult[0].count : 0;
    
    const totalLikesReceived = totalPostLikes + totalCommentLikes;

    const totalCommentsWritten = await commentsModel.countDocuments({ author: userId });
    const followersCount = await userModel.findById(userId).then(u => u.follower.length);
    
    
    console.log(`User ${user.userName} Data:`, { totalLikesReceived, totalCommentsWritten });
    
    res.render('dashboard', { 
        user: user,
        totalLikes: totalLikesReceived,
        totalComments: totalCommentsWritten,
        followersCount: followersCount
    });
});

app.get('/search', async (req, res) => {
  const query = req.query.q?.trim();
  
  if (!query) {
    return res.render('search-results', { users: [], searchQuery: '' });
  }

  try {
    // Search by username, name, location, or jobTitle (case-insensitive)
    const users = await userModel.find({
      $or: [
        { userName: { $regex: query, $options: 'i' } },
        { name: { $regex: query, $options: 'i' } },
        { location: { $regex: query, $options: 'i' } },
        { jobTitle: { $regex: query, $options: 'i' } }
      ]
    }).select('name userName profileImage jobTitle location bio');

    res.render('search-results', { users, searchQuery: query });
  } catch (err) {
    console.error("Error searching users:", err);
    res.status(500).send("Internal Server Error");
  }
});

app.get('/search-profile/:id', isLoggedIn, async (req, res) => {
  try {
    const user = await userModel.findById(req.params.id)
      .populate('following', 'userName profileImage')
      .populate('follower', 'userName profileImage')
      .populate({
    path: 'posts',           
    options: { sort: { createdAt: -1 } } 
  });


      const followersCount = await userModel.findById(user._id).then(u => u.follower.length);

    if (!user) return res.status(404).send("User not found");

    const loggedInUser = await userModel.findOne({ email: req.user.email });
    res.render('search-profile', { user, loggedInUserId: loggedInUser._id.toString(), followersCount });
  } catch (error) {
    console.error("Error searching users:", error);
    res.status(500).send("Internal Server Error");
  }
});


app.get('/login',(req,res)=>{
  res.render("login")
})

app.get('/register',(req,res)=>{
    res.render('register')
})

app.get("/contact", (req,res)=>{
  res.render("contact")
})
app.get('/profile/edit', isLoggedIn,  async (req,res)=>{
    const user = await userModel.findOne({email:req.user.email})
    res.render('edit-profile', { user })
})

app.get("/user/:id/view-all-posts", isLoggedIn, async (req, res) => {
  const posts = await postModel.find({ author: req.params.id })
    .populate('author')
    .sort({ createdAt: -1 });

  // Extract username from req.user
  const userName = req.user.userName;

  res.render('view-all-posts', { posts, userName, token: req.cookies.token });
});


app.get("/user/:id/view-all-posts-of-writer", isLoggedIn, async (req, res) => {
  const posts = await postModel.find({ author: req.params.id })
    .populate('author')
    .sort({ createdAt: -1 });
    const user = await userModel.findById(req.params.id);


  res.render('view-all-posts-of-writer', { posts, user:user, userName: user.userName });
});


app.get("/post/edit/:id", isLoggedIn,  async (req,res)=>{
    const post = await postModel.findById(req.params.id).populate('author')
    res.render('edit-post', { post })
})

app.get("/single-blog/:id", isLoggedIn, async (req, res) => {
  try {
    const post = await postModel
      .findById(req.params.id)
      .populate("author")
      .populate("likes")
      .populate({
        path: "comments",
        populate: { path: "author", select: "userName profileImage" }
      });

    if (!post) {
      return res.status(404).send("Post not found");
    }

    const user = await userModel.findOne({ email: req.user.email });

    res.render("single-blog", { post, user });
  } catch (error) {
    console.error("Error loading single blog:", error);
    res.status(500).send("Server error");
  }
});


app.get('/write-post', isLoggedIn, (req,res)=>{
  res.render("write-post")
})

app.get('/profile',  isLoggedIn, async (req,res)=>{
   const {userName,email} = req.user

   const userDetails = await userModel.findOne({email:email})
        .populate('posts')
        .populate('follower', 'userName profileImage') 
        .populate('following', 'userName profileImage');

    res.render('profile', { user: userDetails })
})

app.get('/logout',(req,res)=>{
   res.cookie("token","")
   res.redirect('/login')
})

app.post("/user/:id/follow", isLoggedIn, async (req, res) => {
  try {
    const targetUserId = req.params.id;
    const currentUser = await userModel.findOne({ email: req.user.email });
    if (!currentUser) return res.status(404).send("Your account not found");
    if (currentUser._id.toString() === targetUserId)
      return res.status(400).send("You cannot follow yourself");

    const targetUser = await userModel.findById(targetUserId);
    if (!targetUser) return res.status(404).send("User not found");

    if (!currentUser.following.includes(targetUserId)) {
      currentUser.following.push(targetUserId);
    }
    if (!targetUser.follower.includes(currentUser._id)) {
      targetUser.follower.push(currentUser._id);
    }

    await currentUser.save();
    await targetUser.save();

    res.json({
      success: true,
      following: true,
      message: "Followed successfully",
    });
  } catch (error) {
    console.error("Error in follow route:", error);
    res.status(500).send("Internal Server Error");
  }
});

 app.post("/user/:id/unfollow", isLoggedIn, async (req, res) => {
  try {
    const targetUserId = req.params.id;
    const currentUser = await userModel.findOne({ email: req.user.email });
    if (!currentUser) return res.status(404).send("Your account not found");

    const targetUser = await userModel.findById(targetUserId);
    if (!targetUser) return res.status(404).send("User not found");

    if (currentUser.following.includes(targetUserId)) {
      currentUser.following = currentUser.following.filter(
        (id) => id.toString() !== targetUserId
      );
      targetUser.follower = targetUser.follower.filter(
        (id) => id.toString() !== currentUser._id.toString()
      );
      await currentUser.save();
      await targetUser.save();
    }

    res.json({
      success: true,
      following: false,
      message: "Unfollowed successfully",
    });
  } catch (error) {
    console.error("Error in unfollow route:", error);
    res.status(500).send("Internal Server Error");
  }
});

app.post("/create-user", async(req,res)=>{
    const secretKey = "abcd";
    const{userName,name, email, password, age} = req.body
    try {
        //fetching details from database
        const user = await userModel.findOne({email:email})
    if(user){
      req.flash('error', 'User already exists');
      return res.redirect('/register');
    }
        else{
            const salt = bcrypt.genSaltSync(10);
            const hashedPassword = bcrypt.hashSync(password, salt);
            //creating new user in database
            const newUser = await userModel.create({
                userName,
                name, 
                email, 
                password:hashedPassword,
                age
            })
            
            // setting up cookie
            const token = await jwt.sign({userName:newUser.userName, email:newUser.email}, secretKey)
            res.cookie("token", token)
            console.log("user created successfully", newUser);
            req.flash('success', 'Account created successfully');
            res.redirect('/profile');
        }
    } catch (error) {
        console.error("Error creating user:", error);
        res.status(500).send("Internal Server Error");
    }
})

app.post('/login-user', async(req,res)=>{
    const {email,password} = req.body
    const secretKey = "abcd";

    try {
        const userExists = await userModel.findOne({email: email})
    if(!userExists){
      req.flash('error', 'User not found');
      return res.redirect('/login');
    }
    else{
            const isMatch = await bcrypt.compare(password, userExists.password)
            if (!isMatch) {
        req.flash('error', 'Incorrect password');
        return res.redirect('/login');
            } else {
                // password is correct, now set cookies
                const token = await jwt.sign({userName:userExists.userName, email:userExists.email}, secretKey,)
                res.cookie("token", token)
        req.flash('success', 'Logged in successfully');
        res.redirect("/profile")
    
            }
        }
    } catch (error) {
        console.error("Error logging in user:", error);
        res.status(500).send("Internal Server Error");
    }
})

app.post("/send-contact", async (req, res) => {
  const { name, email, message } = req.body;

  try {
    console.log("Contact Form Submission:");
    console.log("Name:", name);
    console.log("Email:", email);
    console.log("Message:", message);
    res.redirect("/");
  } catch (error) {
    console.error("Error in contact form submission:", error);
    res.status(500).send("Internal Server Error");
  }
});
app.post('/create-post', isLoggedIn, async(req,res)=>{
    const {title, content} = req.body
    const {userName, email} = req.user

    try {
        const user = await userModel.findOne({email:email})
    
    
        const newPost = await postModel.create({
        author: user._id,
        title,
        content
    });
    
       user.posts.push(newPost._id);
       await user.save();
    
        res.redirect('/profile')
    } catch (error) {
        console.error("Error creating post", error);
        res.status(500).send("Internal Server Error");
    }

})


app.post('/profile/update/:id', isLoggedIn, upload.single('profileImage'), async(req,res)=>{
    const {name, jobTitle, location, bio } =req.body
    const id = req.params.id
    const profileImage = req.file ? req.file.path : null;

    try {
        const updatedData = { name, jobTitle, location, bio }
        if(profileImage){
            updatedData.profileImage = profileImage
        }

        await userModel.findByIdAndUpdate(id, updatedData)
        res.redirect('/profile')

    } catch (error) {
        console.error("Error logging in user:", error);
        res.status(500).send("Internal Server Error");
    }
})

app.post("/post/delete/:id", isLoggedIn, async (req,res)=> {
  await postModel.findByIdAndDelete(req.params.id);
  res.redirect('/profile');
});

app.post("/post/:postId/comment", isLoggedIn, async (req, res) => {
  const { content } = req.body;
  const postId = req.params.postId;
  const author = await userModel.findOne({ email: req.user.email });

  if (!author) {
    return res.status(404).send("Author not found");
  }

  const newComment = await commentsModel.create({
    post: postId,
    author: author._id,
    content,
  });

  // Add the comment to the post's comments array
  await postModel.findByIdAndUpdate(postId, {
    $push: { comments: newComment._id },
  });

  res.redirect(`/single-blog/${postId}`);
});

app.post("/post/:postId/like", isLoggedIn, async (req, res) => {
  try {
    const post = await postModel.findById(req.params.postId);
    if (!post) return res.status(404).send("Post not found");

    const user = await userModel.findOne({ email: req.user.email });
    if (!user) return res.status(404).send("User not found");

    const userIdStr = user._id.toString();

    post.likes = post.likes.filter(l => l);

    if (!post.likes.some(l => l.toString() === userIdStr)) {
      post.likes.push(user._id);
      await post.save();
    }

    res.redirect(`/single-blog/${req.params.postId}`);
  } catch (error) {
    console.error("Like error:", error);
    res.status(500).send("Server error");
  }
});

app.post("/post/:postId/dislike", isLoggedIn, async (req, res) => {
  try {
    const post = await postModel.findById(req.params.postId);
    if (!post) return res.status(404).send("Post not found");

    const user = await userModel.findOne({ email: req.user.email });
    if (!user) return res.status(404).send("User not found");

    // Remove user from likes
    post.likes = post.likes.filter(
      (likeId) => likeId.toString() !== user._id.toString()
    );

    await post.save();

    res.redirect(`/single-blog/${req.params.postId}`);
  } catch (error) {
    console.error("Dislike error:", error);
    res.status(500).send("Server error");
  }
});



// middleware to verify token

async function isLoggedIn(req, res, next) {
    const secretKey = "abcd";
    const token = req.cookies?.token;
    if(token===""){
        return res.status(401).render("login");
    }
    
  else{
    try {
      const payloadData = await jwt.verify(token, secretKey)
      req.user = payloadData
      next()
    } catch (error) {
      console.error("Error verifying token:", error);
      req.flash('error', 'Please login to continue');
      return res.redirect('/login');
    }

  }
}


app.listen(process.env.PORT, () => {
    console.log(`Server is running on "http://localhost:${process.env.PORT}"`);
})