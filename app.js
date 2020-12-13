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
const fsPromises = fs.promises;
const util = require('util');
const exec = util.promisify(require('child_process').exec);
const readline = require('readline');

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

const getLines = async(text_path) => {
    const fileStream = fs.createReadStream(`${text_path}`);
      
    const rl = readline.createInterface({
        input: fileStream,
        crlfDelay: Infinity
    });

    return rl;
}


// test exec function, not production use
app.get('/test-run', async (req, res) => {

    // let user = req.user.id
    let user = {}
    user.id = "t12d8s"

    let err_string = ""
    let out_string = ""
    let body = ""

    let script_name = "LobbySetup_Sol"

    body += "== Compiling ==\n"

    try {
        await exec(`javac -encoding ISO-8859-1 ./${user.id}/${script_name}.java`, {timeout:5000});
        body += "Successful\n"
    } catch (e) {
        let err_msg = e
        err_msg = e.stderr
        // err_msg = err_msg.stderr.split('-Dfile.encoding=UTF-8')[1]
        body += "Failure\n"
        err_string += err_msg.trim()
        return res.send({body, out_msg:out_string,err_msg:err_string})
    }

    body += "== Testing Cases =="
    let childProcess = require('child_process').spawn('java', ['-cp',`./${user.id}` , `${script_name}`]);
    setTimeout(function(){ childProcess.kill(); err_string += "Timeout Error\n"}, 5000);    

    
    

    let all_lines = await getLines("./in.txt")
    
    for await (const line of all_lines) {
        // Each line in input.txt will be successively available here as `line`.
        childProcess.stdin.write(line+"\n")
    }
    
    childProcess.stdout.on("data", function (data) {
        if (data.toString().trim() != "" && data.toString().trim() != " ") {
            out_string += data.toString().trim()+"\n";
        }

    });


    childProcess.stderr.on("data", function (data) {
        if (data.toString().trim() != "" || data.toString().trim() != " ") {
            // console.log(data.toString());
            err_string += data.toString().trim()+"\n";
        }
    });

    childProcess.on('exit', async()=>{
        if (process.platform == "win32"){
            try {
                let {stdout, stderr} = await exec("fc out.txt expectedOut.txt")
                if (stdout.includes("no differences")){
                    return res.send({body, out_msg:out_string,err_msg:err_string, success:true})
                }
            } catch(e) {
                return res.send({body, out_msg:out_string,err_msg:err_string, success:false})
            }
        } else {
            try {
                let {stdout, stderr} = await exec("diff -q out.txt expectedOut.txt")
                console.log(stdout, stderr)
            } catch(e){
                console.log(e)
            }
            
            
        }
    })


    // let {stdout2, stderr2 } = await exec('ls')
    // console.log('stdout:', stdout2);
    // console.error('stderr:', stderr2);

    // let cp = await exec('java Test503308789');
    // cp.stdout.on("data", (data)=>{
    //     console.log(data)
    // })

    // let childProcess = require('child_process').spawn(
    //     'java', ['Test503308789']
    // );
    // childProcess.stdout.on('data', function (data) {
    //     if (data.toString().trim() != "" || data.toString().trim() != " ") {
    //         console.log(data.toString());
    //     }

    // });

    // childProcess.stderr.on("data", function (data) {
    //     if (data.toString().trim() != "" || data.toString().trim() != " ") {
    //         console.log(data.toString());
    //     }
    // });
    // // console.log('stdout:', stdout1);
    // console.error('stderr:', stderr1);

})

app.post("/test-upload", upload.single('ok'), async (req, res) => {

    let user = {}
    user.id = "t12d8s"

    let resp = await axios.get(req.file.location)
    let original_pre = req.file.originalname.split('.')[0]
    let post_name = req.file.key.split('.')[0]
    let file_data = resp.data;

    let find = new RegExp(original_pre, 'g')

    file_data = file_data.replace(find, post_name)

    
    try {
        await fsPromises.access(user.id)
    } catch(e){
        await fsPromises.mkdir(user.id)
    }
    // takes replaced file data and outputs file to be used when executing
    fs.writeFile(`./${user.id}/${req.file.originalname}`, file_data, (err) => {
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