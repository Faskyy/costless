const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const axios = require('axios');
const app = express();

app.use(cors()); // Enable CORS
app.use(bodyParser.json());
require('dotenv').config();

let cachedToken;

async function getManagementApiToken() {
  if (cachedToken) {
    return cachedToken;
  }
  console.log(process.env.AUTH0_CLIENT_ID);
  console.log(process.env.AUTH0_CLIENT_SECRET);
  const response = await axios.post(`https://dev-ifjaih1n2zo30qx8.us.auth0.com/oauth/token`, {
    client_id: process.env.AUTH0_CLIENT_ID,
    client_secret: process.env.AUTH0_CLIENT_SECRET,
    audience: 'https://dev-ifjaih1n2zo30qx8.us.auth0.com/api/v2/',
    grant_type: 'client_credentials'
  });
  cachedToken = response.data.access_token;
  return cachedToken;
}

// Set CORS headers for all routes
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', 'http://localhost:5173'); // Replace with your frontend URL
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, DELETE');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  next();
});

app.post('/api/update-user', async (req, res) => {
  const { user_id, first_name, last_name } = req.body;
  try {
    const token = await getManagementApiToken();
    const response = await axios.patch(`https://dev-ifjaih1n2zo30qx8.us.auth0.com/api/v2/users/${user_id}`, {
      user_metadata: { first_name, last_name }
    }, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    res.setHeader('Access-Control-Allow-Origin', 'http://localhost:5173'); // Add this line to set the CORS header in the response
    res.status(200).send(response.data);
  } catch (err) {
    res.status(500).send(err);
  }
});

app.listen(process.env.PORT || 5001, () => console.log('Server is running...'));
