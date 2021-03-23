<?php
   $uid=$_REQUEST['uid'];
   $array_month = [
        "01" => "JAN",
        "02" => "FEB",
        "03" => "MARCH",
        "04" => "APR",
        "05" => "MAY",
        "06" => "JUNE",
        "07" => "JULY",
        "08" => "AUG",
        "09" => "SEP",
        "10" => "OCT",
        "11" => "NOV",
        "12" => "DEC",
   ];
   if (($h = fopen("Lots.csv", "r")) !== FALSE) 
    {
       $year = 0;
    // Convert each line into the local $row variable
      while (($row = fgetcsv($h, 3000, ",")) !== FALSE) 
      {		
          if ($row[0]==$uid){
		$product_info=''.$row[1];
              	$year=substr($product_info,0,2);   
              	$month=substr($product_info,2,2);
		break;
	}
	}?>
<html lang="en"><head>
  <meta charset="utf-8">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Trivicity Health Product Verification</title>
  <link rel="manifest" href="/manifest.json">
  <meta name="theme-color" content="#2F3BA2">
  <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.4.1/jquery.min.js"></script>
  <!-- <script src="https://js.stripe.com/v3/"></script> -->
  <style>

* {
  box-sizing: border-box;
}

html, body {
  padding: 0;
  margin: 0;
  height: 100%;
  width: 100%;
  font-family: 'Helvetica', 'Verdana', sans-serif;
  font-weight: 400;
  font-display: optional;
  color: #444;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

html {
  overflow: hidden;
}

body {
  display: -webkit-box;
  display: -webkit-flex;
  display: -ms-flexbox;
  display: flex;
  -webkit-box-orient: horizontal;
  -webkit-box-direction: normal;
  -webkit-flex-direction: row;
      -ms-flex-direction: row;
          flex-direction: row;
  -webkit-flex-wrap: nowrap;
      -ms-flex-wrap: nowrap;
          flex-wrap: nowrap;
  -webkit-box-pack: start;
  -webkit-justify-content: flex-start;
      -ms-flex-pack: start;
          justify-content: flex-start;
  -webkit-box-align: stretch;
  -webkit-align-items: stretch;
      -ms-flex-align: stretch;
          align-items: stretch;
  -webkit-align-content: stretch;
      -ms-flex-line-pack: stretch;
          align-content: stretch;
  background: #ececec;
}


.main {
  padding: 40px;
  padding-left: 25%;
  margin-left: auto;
  margin-right: auto;
  -webkit-box-flex: 1;
  -webkit-flex: 1;
      -ms-flex: 1;
          flex: 1;
  overflow-x: auto;
  overflow-y: auto;}

    .centered {
      margin-top : 5px;
      margin-bottom: 0px;
      display: block;
      float: left;
    }
    .right {
      margin-left: auto;
      margin-top : 100px;
      margin-bottom: 0px;
      display: block;
    }
  </style>
</head>
<body data-new-gr-c-s-check-loaded="14.984.0" data-gr-ext-installed="">


  <main class="main">
      <div id="start" style="display: none;">
        Product check in progress...
      </div>
<?php 
	if ($year != 0) { 
?>
	<div class="centered">
	      <img id="logo" src="/images/triviciti-health.png" width="{256}" style="">
		<br/>
	      <img id="check" src="/images/fingerprint-accepted.png" width="{256}" height="{256}" style="">
	</div>
	<div class="right">
	      <div id="success" style=""><td> <?php echo 'Your product '.$uid?><?php echo ' is verified'?></td></div>
	      <div id="details" style="">
		<br>
		<td> <?php echo 'Lot Number: '.$product_info?>.</td><br><br>
		Production place: CHANDLER, AZ, USA.<br><br>
		<td> <?php echo 'Production date: '.$array_month[$month]?><?php echo ' 20'.$year?>.</td><br><br>
		<td> <?php echo 'Expiration date: '.$array_month[$month]?><?php echo ' 20'.($year + 2)?>.</td><br><br>
	      </div>
	</div>
      
      <div id="fail" style="display:none;">
        Product check completed. Your product is not verified.
      </div>
      <div id="error" style="display:none;">
        Product check could not be completed. Please try again.
      </div>
<?php
	} else{
?>
	<img id="check" class="centered" src="/images/fingerprint-error.png" width="{256}" height="{256}" style="">
	<div id="details" class="right">
        <br>
        	Product is not authenticated
	</div>
    

  </main>

  <script>
    var url_string = window.location.href;
var url = new URL(url_string);
var uid = url.searchParams.get("uid");
const strSuccess = `Your product ${uid} is verified`;
console.log(strSuccess);
$( "#success" ).text( strSuccess );
if (uid) {
  $("#start").show();
 
  setTimeout(function(){ $("#start").hide(); $("#check").show(); $("#success").show(); $("#logo").show(); $("#details").show(); }, 2000);
}

  </script>


</body></html>
<?php

      }
    }

  // Close the file
  fclose($h); 
?>

