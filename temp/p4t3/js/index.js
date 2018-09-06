// Wait for device API libraries to load
function onLoad() {
  document.addEventListener("deviceready", onDeviceReady, false);


}

// device APIs are available
function onDeviceReady() {
  // Now safe to use device APIs
  $('#cameraTakePicture').click(cameraTakePicture);
}

// Take a picture with the camera
function cameraTakePicture() {
  navigator.camera.getPicture(onSuccess, onFail, {
    quality: 85,
    destinationType: Camera.DestinationType.DATA_URL
  });

  function onSuccess(imageData) {
    $("#myImage").attr("src", "data:image/jpeg;base64," + imageData);
  }

  function onFail(message) {
    alert('Failed because: ' + message);
  }
}
