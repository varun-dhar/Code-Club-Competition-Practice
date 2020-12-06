const mongoose = require("mongoose");
// const crypto = require('crypto');
// const jwt = require('jsonwebtoken');
const Schema = mongoose.Schema;
// const bcrypt = require('bcryptjs')
//Create schema
let ObjectId = Schema.ObjectId;
const ProblemSchema = new Schema({
    name:String,
    description:String,
    max_uploads:Number,
    point_value:Number,
    type:String
    
});

mongoose.model('problems', ProblemSchema);