import feedback_logger

def seed():
    feedback_logger.init_db()
    
    # market_analysis
    # feedback_logger.log_feedback('market_analysis', 'good', 'Market prediction for: Cotton', 'Cotton prices expected to rise 2% due to supply chain issues.', parameter_name='Cotton', prediction_summary='Cotton rise 2%')
    # feedback_logger.log_feedback('market_analysis', 'good', 'Market prediction for: Forex', 'USD/PKR stable at 278.50.', parameter_name='Forex', prediction_summary='USD/PKR stable')
    # feedback_logger.log_feedback('market_analysis', 'bad', 'Market prediction for: Yarn', 'Yarn index will drop by 5%.', parameter_name='Yarn', prediction_summary='Yarn drop 5%')
    # feedback_logger.log_feedback('market_analysis', 'bad', 'Market prediction for: Oil', 'Oil prices spiking to $90.', parameter_name='Oil', prediction_summary='Oil spike $90')
    # feedback_logger.log_feedback('market_analysis', 'bad', 'Market prediction for: ZCE Cotton', 'ZCE futures down 300 points.', parameter_name='ZCE Cotton', prediction_summary='ZCE down 300')
    
    # # email_editor
    # feedback_logger.log_feedback('email_editor', 'good', 'Write outreach to Brand A', 'Dear Brand A, we offer high quality textiles...', tone_requested='Professional', draft_length_chars=250)
    # feedback_logger.log_feedback('email_editor', 'partial', 'Follow up with Brand B', 'Hi, following up on our last talk.', tone_requested='Casual', draft_length_chars=40)
    # feedback_logger.log_feedback('email_editor', 'partial', 'Draft intro for Brand C', 'Hello, we are TEXBase.', tone_requested='Formal', draft_length_chars=25)
    # feedback_logger.log_feedback('email_editor', 'bad', 'Refine email content', 'Very bad draft with many typos.', tone_requested='Direct', draft_length_chars=30)
    
    # # inbox_flow
    # feedback_logger.log_feedback('inbox_flow', 'good', 'Send follow-up to Client X', 'Email sent successfully via Gmail API', pipeline_stage='send')
    # feedback_logger.log_feedback('inbox_flow', 'partial', 'Check for replies', 'Found 2 new messages, failed to categorize 1', pipeline_stage='inbox_read')
    # feedback_logger.log_feedback('inbox_flow', 'bad', 'Trigger next follow-up', 'Error: Template not found', pipeline_stage='followup')
    
    # # po_quotation
    # feedback_logger.log_feedback('po_quotation', 'good', 'Quote for 1000m Denim', 'Predicted: 4.50 USD/m', predicted_price=4.50, item_description='1000m Denim')
    # feedback_logger.log_feedback('po_quotation', 'good', 'Quote for 500kg Yarn', 'Predicted: 3.20 USD/kg', predicted_price=3.20, item_description='500kg Yarn')
    # feedback_logger.log_feedback('po_quotation', 'bad', 'Quote for Silk blend', 'Predicted: 12.00 USD/m', predicted_price=12.0, actual_price=15.5, price_delta=3.5, item_description='Silk blend')
    # feedback_logger.log_feedback('po_quotation', 'bad', 'Quote for Linen', 'Predicted: 8.50 USD/m', predicted_price=8.5, actual_price=6.0, price_delta=2.5, item_description='Linen')

    print(f"Seeded upgraded records into feedback_log.db")

if __name__ == "__main__":
    seed()
