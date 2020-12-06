const express = require("express");
const path = require('path');
const mongoose = require("mongoose");
const bodyParser = require('body-parser');
const methodOverride = require('method-override');
const aws = require('aws-sdk');
const dotenv = require('dotenv');
const { URLSearchParams } = require('url');
// const fileUpload = require('express-fileupload');
var multer = require('multer')
// let upload = multer({dest:"uploads/"})
const multerS3 = require('multer-s3');
const passport = require('passport')
const flash = require('express-flash')
require('./models/User')
require('./models/Problem')
const User = mongoose.model('users')
const Problem = mongoose.model('problems')
const session = require('express-session')
const ws = require('ws')
const { ensureAuthenticated, checkAuth, checkAdmin } = require('./helpers/auth')
const { databaseUri, port, staticDir } = require('./env')
const axios = require('axios').default
const app = express();
const fs = require('fs')
const util = require('util');
const exec = util.promisify(require('child_process').exec);

// Map global promise - depreciation warning
mongoose.Promise = global.Promise;
//Connect to mongoose
mongoose.connect(`${databaseUri}`, {
    useNewUrlParser: true,
    useUnifiedTopology: true
})
    .then(() => console.log("Connected to mongoDb"))
    .catch(err => console.log(err));

//Body parser middle ware
app.use(bodyParser.json({ limit: '50mb', extended: true }))
app.use(bodyParser.urlencoded({ limit: '50mb', extended: true }))
// app.use(cookieParser());
app.disable('x-powered-by');
app.use(session({
    secret: 'jhg89sdgj3wigj2iogj',
    resave: false,
    saveUninitialized: false
}))
app.use(passport.initialize())
app.use(passport.session())
require('./config/passport')(passport);
// app.use(fileUpload)
// app.use(fileUpload({
//     createParentPath: true
// }));
// app.set('trust proxy', 1);


app.get("/", async (req, res) => {
    res.sendFile(path.join(__dirname, `./${staticDir}`, 'main.html'));
})

app.get("/dash", ensureAuthenticated, async (req, res) => {
    // POPULATE PROBLEMS IN UPLOADS
    // let user = await User.findById(req.user.id).populate('uploads.problem')
    // await user.populate('uploads.0.problem')
    // console.log(user.uploads[0].problem)

    res.sendFile(path.join(__dirname, `./${staticDir}`, 'dash.html'));
})


app.post('/login', async (req, res, next) => {

    return passport.authenticate('user-login', { session: true, failureRedirect: '/login' }, (err, passportUser, info) => {
        console.log(err, info)
        if (err) {
            return next(err);
        }
        if (passportUser) {
            const user = passportUser;
            // MANUAL CALL LOGIN ### IMPORTANT
            req.logIn(user, function (err) {
                if (err) { return next(err); }
                return res.json({ success: true, redirect_url: "/dash" })
            });

        } else {
            return res.json({ success: false, message: info.message })
        }
    })(req, res, next);
})


app.get('/logout', async (req, res) => {
    req.logout();
    res.redirect('/login')
})

app.get('/reg', async (req, res) => {
    res.sendFile(path.join(__dirname, `./${staticDir}`, 'register.html'));
})

app.get('/login', checkAuth, async (req, res) => {
    res.sendFile(path.join(__dirname, `./${staticDir}`, 'login.html'));
})

app.get('/leaderboard', async (req, res) => {
    res.sendFile(path.join(__dirname, `./${staticDir}`, 'leaderboard.html'));
})


const s3 = new aws.S3();
const upload = multer({
    storage: multerS3({
        s3,
        bucket: 'codeclubcomp',
        acl: 'public-read',
        key: function (req, file, cb) {
            let rand = parseInt(Math.random() * 1000000000, 11)
            let [pre, ext] = file.originalname.split('.')
            // console.log(pre, ext)
            file_name = `${pre}${rand}.${ext}`
            cb(null, file_name)
        }
    }),
    limits: { fileSize: 10 * 1024 * 1024 },
})

app.get('/test-upload', async (req, res) => {
    res.sendFile(path.join(__dirname, `./${staticDir}`, 'test.html'));
})

// test exec function, not production use
app.get('/test-run', async(req,res)=>{
    
    let { stdout, stderr } = await exec('javac Test503308789.java');
    console.log('stdout:', stdout);
    console.error('stderr:', stderr);

    let {stdout2, stderr2 } = await exec('ls')
    console.log('stdout:', stdout2);
    console.error('stderr:', stderr2);

    let { stdout1, stderr1 } = await exec('java Test503308789');
    console.log('stdout:', stdout1);
    console.error('stderr:', stderr1);
    res.send(stdout1)


})

app.post("/test-upload", upload.single('ok'),  async(req,res)=>{
    let resp = await axios.get(req.file.location)
    let original_pre = req.file.originalname.split('.')[0]
    let post_name = req.file.key.split('.')[0]
    let file_data = resp.data;

    let find = new RegExp(original_pre, 'g')

    file_data = file_data.replace(find, post_name)
    
    // takes replaced file data and outputs file to be used when executing
    fs.writeFile(req.file.key, file_data, (err)=>{
        if (err) throw err;

        console.log("Written")
    })

    res.redirect('/test-upload')
})


app.post('/upload-program', upload.single('p1'), async (req, res) => {

    if (!req.file) {

    }

    // let user = await User.findById(req.user.id).populate('uploads.problem')
    // await user.populate('uploads.0.problem')
    // console.log(user.uploads[0].problem)

    let user = req.user
    let problem = await Problem.findById(req.body.problem)
    console.log(problem.max_uploads)
    let file_url = req.file.location
    // console.log(file_url)
    // req.user.uploads.forEach(upload => {
    //     console.log(upload.problem)
    // });

    let curr_uploads = user.uploads.filter(x => x.problem._id == req.body.problem)
    if (curr_uploads.length == problem.max_uploads) { return res.json({ success: false, message: "You already have the max attempts for this problem!" }) }

    let upload = {
        problem: req.body.problem,
        location: file_url,
        attempt: curr_uploads.length + 1,

    }

    user.uploads.push(upload)

    await user.save()

    res.redirect('/dash')

})

// app.use('/register', require('./api/register'))

const socketServer = new ws.Server({ port: 3030 });

socketServer.on('connection', (socketClient) => {
    console.log("connected")
    console.log("client Set Length: ", socketServer.clients.size)

    // socketClient.on('message', ()=>{
    //     socketServer.clients.forEach((client) => {
    //         let message = "Hello sirs"
    //         console.log(JSON.stringify([message]))
    //         if (client.readyState === ws.OPEN) {
    //             client.send(JSON.stringify([message]));
    //         }
    //     });
    // })
        

    socketClient.on('close', (socketClient) => {
        console.log('closed')
        console.log("Number of clients: ", socketServer.clients.size)
    })
})

// setInterval(function(){
//     socketServer.clients.forEach((client) => {
//         let message = "Hello Test"
//         if (client.readyState === ws.OPEN) {
//             client.send(JSON.stringify([message]));
//         }
//     });
// }, 3000)



app.listen(port || 3000, () => {
    console.info("Running on port 3000");

});