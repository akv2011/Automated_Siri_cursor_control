
// Twilio Function to trigger webhook when SMS is sent
// Deploy this as a Twilio Function

exports.handler = function(context, event, callback) {
    const axios = require('axios');
    
    // Your webhook URL
    const webhookUrl = 'https://c85d8a437f93.ngrok-free.app/sms';
    
    // Extract SMS data
    const messageBody = event.Body || '';
    const fromNumber = event.From || '';
    const toNumber = event.To || '';
    
    // Forward to your webhook
    axios.post(webhookUrl, {
        Body: messageBody,
        From: fromNumber,
        To: toNumber
    })
    .then(response => {
        console.log('Webhook triggered successfully');
        callback(null, { success: true });
    })
    .catch(error => {
        console.error('Error triggering webhook:', error);
        callback(error);
    });
};
