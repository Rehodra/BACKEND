const multer = require('multer');
const { CloudinaryStorage } = require('multer-storage-cloudinary');
const cloudinary = require('./cloudinary'); // path to config/cloudinary.js

const storage = new CloudinaryStorage({
  cloudinary,
  params: {
    folder: 'nimi_blog',                   
    allowed_formats: ['jpg', 'jpeg', 'png'],
    transformation: [{ width: 1200, crop: 'limit' }], 
  },
});

const upload = multer({ storage });

module.exports = upload;
