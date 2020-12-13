const path = require('path');


const fs = require('fs')
const fsPromises = fs.promises;
const util = require('util');
const exec = util.promisify(require('child_process').exec);
const execFile = util.promisify(require('child_process').execFile);
const readline = require('readline');

const getLines = async(text_path) => {
    const fileStream = fs.createReadStream(`${text_path}`);
      
    const rl = readline.createInterface({
        input: fileStream,
        crlfDelay: Infinity
    });

    return rl;
}

let script_name = "LobbySetup_TimeoutErr";

(async () => {
    let user = {}
    user.id = "t12d8s"

    console.log("== Compiling ==")

    try {
        await exec(`javac -encoding ISO-8859-1 ./${user.id}/${script_name}.java`);
        console.log("Successful")
    } catch (e) {
        let err_msg = e
        err_msg = e.stderr
        // err_msg = err_msg.stderr.split('-Dfile.encoding=UTF-8')[1]
        console.log(err_msg)
        return
    }

    console.log("== Testing Cases ==")
    // let program = await exec('sh ./bash/scriptRun.sh')
    // console.log(program.stdout)
    let childProcess = require('child_process').spawn(
        'java', ['-cp',`./${user.id}` , `${script_name}`]
    );
    // childProcess.stdin.write("13\n")
    // childProcess.stdin.write("\n")
    childProcess.stdout.on('data', function (data) {
        if (data.toString().trim() != "" && data.toString().trim() != " ") {
            console.log(data.toString().trim());
        }

    });

    childProcess.stderr.on("data", function (data) {
        if (data.toString().trim() != "" || data.toString().trim() != " ") {
            console.log(data.toString());
        }
    });

    let all_lines = await getLines("./in.txt")
    
    for await (const line of all_lines) {
        // Each line in input.txt will be successively available here as `line`.
        childProcess.stdin.write(line+"\n")
    }

    childProcess.on('exit', async()=>{
        if (process.platform == "win32"){
            let {stdout, stderr} = await exec("fc out.txt expectedOut.txt")
    
            console.log(stdout)
        } else {
            let {stdout, stderr} = await exec("diff out.txt expectedOut.txt")
            console.log(stdout)
        }
    })
    

})()
