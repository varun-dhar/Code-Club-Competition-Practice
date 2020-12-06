const mongoose = require("mongoose");
// const crypto = require('crypto');
// const jwt = require('jsonwebtoken');
const Schema = mongoose.Schema;
// const bcrypt = require('bcryptjs')
//Create schema
let ObjectId = Schema.ObjectId;
const UploadSchema = new Schema({
    problem:String,
    user:String,
    location:String,
    attempt:Number
    
});

mongoose.model('uploads', UploadSchema);