module.exports = {
    ensureAuthenticated: function(req, res, next){
        console.log(req.isAuthenticated())
        if(req.isAuthenticated()){
            return next();
        }
        // req.flash('error', 'Not authorized');
        res.redirect('/login')  
    },

    checkAuth: function(req, res, next){
        if(req.isAuthenticated()){
            res.redirect('/dash')  
        } else {
            return next();
        }
        
    },
    checkAdmin: function(req, res, next){
        try {
            req.session.passport.user.userGroup;
        } catch (err){
            req.flash("error", "You shouldn't be here! You are not an admin!");
            res.redirect("/dashboard/login");
            return;
        }
        if (req.session.passport.user.userGroup === "admin"){
            return next();
        } else {
            req.flash("error", "You shouldn't be here! You are not an admin!");
            res.redirect("/dashboard/login");
        }
    }
}

