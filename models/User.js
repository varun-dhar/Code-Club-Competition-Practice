const mongoose = require("mongoose");
// const crypto = require('crypto');
// const jwt = require('jsonwebtoken');
const Schema = mongoose.Schema;
// const bcrypt = require('bcryptjs')
//Create schema
let ObjectId = Schema.ObjectId;
const UserSchema = new Schema({
    email: {
        type: String,
        required: true
    },
    name: {
        type: String,
        required: true
    },
    enrolled_in: {
        competitive: {
            type: Boolean,
            default: false
        },
        debug: {
            type: Boolean,
            deault: false
        }
    },
    uploads: [{
        problem: {type:mongoose.Types.ObjectId, ref:'problems'},
        // user: String,
        location: String,
        attempt: Number,
        submitted: {
            type: Boolean,
            default: false
        },
        status: String,
        // checked_by_judge: {
        //     type: Boolean,
        //     default: false
        // },
        correct: Boolean,
    }]

});

mongoose.model('users', UserSchema);