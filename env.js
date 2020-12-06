const dotenv = require('dotenv');
dotenv.config();
module.exports = {
    port: process.env.PORT,
    databaseUri: process.env.databaseUri,
    staticDir: process.env.STATIC_DIR,
    awsRegion: process.env.AWS_REGION,
    awsAccessID: process.env.AWS_ACCESS_KEY_ID,
    awsAccessKey: process.env.AWS_SECRET_ACCESS_KEY



    //   cmkARN:process.env.CMK_ARN,

    //   invitecode:process.env.INVITECODE,
    //   stripe_sk:process.env.STRIPE_PRIVATE,
    //   webhook_url:process.env.WEBHOOKURL,
    //   staticDir:process.env.STATIC_DIR,
    //   domain:process.env.DOMAIN,
    //   stripe_pk:process.env.STRIPE_PUBLIC,
    //   affiliate_signing_secret:process.env.AFFILIATE_SIGNING_SECRET
};