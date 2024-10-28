from flask import Flask, render_template, request, redirect, url_for, flash
import boto3
import uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Needed for flash messages

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')  # Update to your region
flights_table = dynamodb.Table('Flights')
bookings_table = dynamodb.Table('Bookings')

# Initialize SES for sending emails
ses_client = boto3.client('ses', region_name='us-east-1')  # Update to your region

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/search_flights', methods=['GET', 'POST'])
def search_flights():
    if request.method == 'POST':
        departure_city = request.form['departure_city']
        destination_city = request.form['destination_city']
        flight_date = request.form['flight_date']  # Get the flight date from the form

        # Query flights based on departure and destination cities
        response = flights_table.scan(
            FilterExpression="DepartureCity = :dep and DestinationCity = :dest and FlightDate = :date",
            ExpressionAttributeValues={
                ":dep": departure_city,
                ":dest": destination_city,
                ":date": flight_date  # Use the flight date in the query
            }
        )
        flights = response['Items']
        return render_template('flights.html', flights=flights)
    return render_template('search_flights.html')

@app.route('/book_flight/<string:flight_id>', methods=['GET', 'POST'])
def book_flight(flight_id):
    if request.method == 'POST':
        user_email = request.form['email']
        user_name = request.form['name']
        booking_id = str(uuid.uuid4())  # Unique booking ID
        booking_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Fetch current flight details
        response = flights_table.get_item(Key={'FlightID': flight_id})
        flight = response.get('Item', {})

        # Check if there are available seats
        available_seats = int(flight.get('AvailableSeats', 0))
        if available_seats > 0:
            # Save booking details in DynamoDB
            bookings_table.put_item(
                Item={
                    'BookingID': booking_id,
                    'FlightID': flight_id,
                    'UserEmail': user_email,
                    'UserName': user_name,
                    'BookingDate': booking_date,
                    'Status': 'Confirmed'
                }
            )

            # Decrease available seats by 1
            flights_table.update_item(
                Key={'FlightID': flight_id},
                UpdateExpression="SET AvailableSeats = AvailableSeats - :decr",
                ExpressionAttributeValues={":decr": 1}
            )

            # Send SES email for booking confirmation
            ses_client.send_email(
                Source='bmary202422@gmail.com',  # Replace with your verified email
                Destination={
                    'ToAddresses': [user_email]
                },
                Message={
                    'Subject': {
                        'Data': 'Flight Booking Confirmation'
                    },
                    'Body': {
                        'Text': {
                            'Data': f"Dear {user_name},\n\nYour booking (ID: {booking_id}) has been confirmed! Thank you for choosing SB FlightConnect.\n\nSafe travels!"
                        }
                    }
                }
            )

            flash('Booking confirmed! A confirmation email has been sent.')
            return redirect(url_for('thank_you', name=user_name))
        else:
            flash('Sorry, no available seats left for this flight.')
            return redirect(url_for('search_flights'))

    # Fetch flight details for display
    response = flights_table.get_item(Key={'FlightID': flight_id})
    flight = response.get('Item', {})
    
    return render_template('book_flight.html', flight=flight)
@app.route('/thank_you')
def thank_you():
    user_name = request.args.get('name')  # Get the name from the URL query parameters
    return render_template('thank_you.html', name=user_name)

@app.route('/admin')
def admin_dashboard():
    # Retrieve all flights and bookings
    flights = flights_table.scan().get('Items', [])
    bookings = bookings_table.scan().get('Items', [])
    return render_template('admin_dashboard.html', flights=flights, bookings=bookings)

if __name__ == '__main__':
    app.run(debug=True)
