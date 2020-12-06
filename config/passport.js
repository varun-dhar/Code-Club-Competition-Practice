const LocalStrategy = require('passport-local').Strategy;
const mongoose = require('mongoose');
// const bcrypt = require('bcryptjs');

//Load models
const User = mongoose.model('users')
// const Admin = mongoose.model('admins')


module.exports = function (passport) {
    passport.use("user-login", new LocalStrategy({ usernameField: "email", pw:"password" }, async(useremail,not, done) => {
        // matched key
        let user = await User.findOne({email:useremail})
        if (!user) {
            return done(null, false, { message: "Could not find your registration. Please try with a different email" });
        }
        return done(null, user)
    }));

    // passport.use("admin", new LocalStrategy({ usernameField: "user", passwordField: "password" }, (user, password, done) => {
    //     // matched key
    //     Admin.findOne({
    //         user:user
    //     }).then(user => {
    //         if (!user) {
    //             return done(null, false, { message: "Invalid"});
    //         }
    //         if (password == user.password){
    //             return done(null, user)
    //         }


    //     })
    // }));

    // passport.serializeUser(function (user, done) {
    //     done(null, user.id);
    //     if (isUser(user)) {
    //         // serialize user
    //       } else if (isSponsor(user)) {
    //         // serialize company
    //       }
    // });

    // passport.deserializeUser(function (id, done) {
    //     Key.findById(id, function (err, key) {
    //         done(err, key);
    //     });
    // });
    function SessionConstructor(userId, userGroup, details) {
        this.userId = userId;
        this.userGroup = userGroup;
        this.details = details;
    }

    passport.serializeUser(async function (user, done) {
        // let userPrototype = Object.getPrototypeOf(userObject);

        // if (userPrototype === Key.prototype) {
        //     userGroup = "user";
        // } else if (userPrototype === Admin.prototype) {
        //     userGroup = "admin";
        // }

        // let sessionConstructor = new SessionConstructor(userObject.id, userGroup, '');
        done(null, user.id);
    });

    passport.deserializeUser(async function (id, done) {
        // console.log(id)

        // if (sessionConstructor.userGroup == 'user') {
        //     Key.findById(sessionConstructor.userId, function (err, user) {
        //         done(err, user);
        //     });
        // } else if (sessionConstructor.userGroup == 'admin') {
        //     Admin.findById(sessionConstructor.userId, function (err, user) {
        //         done(err, user);
        //     });
        // }
        // console.log('hereb')
        // let user = await User.findById(id)
        // if (!user){
        //    done(err, user)
        // } else {
        //     done(null, user)
        // }

        User.findById(id, function(err, user) {
            done(err, user);
        });
    });
}