import streamlit as st
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
import io
from datetime import datetime
import plotly.graph_objects as go
import plotly.io as pio
import base64
from PIL import Image as PILImage

class ReportFormatter:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.custom_styles = {}
        self.page_size = A4
        self.orientation = 'portrait'
        self.margins = (0.5*inch, 0.5*inch, 0.5*inch, 0.5*inch)  # left, right, top, bottom
        self.header_image = None
        self.footer_text = None
        self.title_style = None
        self.table_style = None
        self.chart_size = (6*inch, 4*inch)
        
    def _resize_image(self, uploaded_file, max_width=6*inch, max_height=2*inch):
        """Resize the uploaded image to fit within the specified dimensions"""
        try:
            # Read the image using PIL
            image = PILImage.open(uploaded_file)
            
            # Calculate aspect ratio
            aspect_ratio = image.width / image.height
            
            # Calculate new dimensions maintaining aspect ratio
            if aspect_ratio > max_width / max_height:  # Width is the limiting factor
                new_width = max_width
                new_height = max_width / aspect_ratio
            else:  # Height is the limiting factor
                new_height = max_height
                new_width = max_height * aspect_ratio
            
            # Resize image
            image = image.resize((int(new_width), int(new_height)), PILImage.Resampling.LANCZOS)
            
            # Save to bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format=image.format or 'PNG')
            img_byte_arr.seek(0)
            
            return Image(img_byte_arr, width=new_width, height=new_height)
        except Exception as e:
            st.error(f"Error processing image: {str(e)}")
            return None

    def show_formatting_interface(self, df):
        """Show the report formatting interface in Streamlit"""
        st.title("📋 Report Formatting")
        
        # Create tabs for different formatting sections
        tabs = st.tabs(["Layout", "Styles", "Content", "Preview"])
        
        with tabs[0]:
            self._show_layout_options()
            
        with tabs[1]:
            self._show_style_options()
            
        with tabs[2]:
            self._show_content_options(df)
            
        with tabs[3]:
            self._show_preview(df)
    
    def _show_layout_options(self):
        """Show layout configuration options"""
        st.subheader("📐 Page Layout")
        
        col1, col2 = st.columns(2)
        with col1:
            # Page size selection
            page_size = st.selectbox(
                "Page Size",
                ["A4", "Letter", "Legal"],
                help="Select the page size for your report"
            )
            self.page_size = A4 if page_size == "A4" else letter
            
            # Orientation selection
            orientation = st.radio(
                "Orientation",
                ["Portrait", "Landscape"],
                help="Choose the page orientation"
            )
            self.orientation = orientation.lower()
        
        with col2:
            # Margins
            st.write("Margins (inches)")
            margin_left = st.number_input("Left", 0.1, 2.0, 0.5, 0.1)
            margin_right = st.number_input("Right", 0.1, 2.0, 0.5, 0.1)
            margin_top = st.number_input("Top", 0.1, 2.0, 0.5, 0.1)
            margin_bottom = st.number_input("Bottom", 0.1, 2.0, 0.5, 0.1)
            self.margins = (margin_left*inch, margin_right*inch, margin_top*inch, margin_bottom*inch)
        
        # Header and Footer
        st.subheader("🖼️ Header & Footer")
        header_image = st.file_uploader(
            "Upload Header Image (optional)",
            type=['png', 'jpg', 'jpeg'],
            help="Upload a logo or header image (will be automatically resized to fit)"
        )
        if header_image:
            # Get available width for image (page width minus margins)
            available_width = (self.page_size[0] if self.orientation == 'portrait' else self.page_size[1]) - self.margins[0] - self.margins[1]
            self.header_image = self._resize_image(header_image, max_width=available_width)
            if self.header_image:
                st.success("Header image processed successfully!")
        
        self.footer_text = st.text_input(
            "Footer Text",
            value="Generated by Tableau Data Reporter",
            help="Enter text to appear in the footer"
        )
    
    def _show_style_options(self):
        """Show style configuration options"""
        st.subheader("🎨 Styling Options")
        
        # Title styling
        st.write("Title Style")
        title_font = st.selectbox("Title Font", ["Helvetica", "Times-Roman", "Courier"])
        title_size = st.slider("Title Size", 12, 36, 24)
        title_color = st.color_picker("Title Color", "#000000")
        title_alignment = st.radio("Title Alignment", ["Left", "Center", "Right"], horizontal=True)
        
        alignment_map = {"Left": TA_LEFT, "Center": TA_CENTER, "Right": TA_RIGHT}
        self.title_style = ParagraphStyle(
            'CustomTitle',
            fontName=title_font,
            fontSize=title_size,
            textColor=colors.HexColor(title_color),
            alignment=alignment_map[title_alignment],
            spaceAfter=30
        )
        
        # Table styling
        st.write("Table Style")
        table_header_color = st.color_picker("Header Background", "#2d5d7b")
        table_row_color = st.color_picker("Alternate Row Color", "#f5f5f5")
        table_font_size = st.slider("Table Font Size", 8, 14, 10)
        
        self.table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(table_header_color)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), table_font_size),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor(table_row_color)),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), table_font_size-2),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#808080')),
            ('ROWHEIGHT', (0, 0), (-1, -1), 20),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])
        
        # Chart styling
        st.write("Chart Size")
        chart_width = st.slider("Chart Width (inches)", 4, 10, 6)
        chart_height = st.slider("Chart Height (inches)", 3, 8, 4)
        self.chart_size = (chart_width*inch, chart_height*inch)
    
    def _show_content_options(self, df):
        """Show content selection and ordering options"""
        st.subheader("📝 Content Selection")
        
        # Report Title
        report_title = st.text_input(
            "Report Title",
            value="Data Report",
            help="Enter the title that will appear at the top of your report"
        )
        
        # Column selection and ordering
        st.write("Select and order columns to include:")
        selected_columns = st.multiselect(
            "Columns",
            df.columns.tolist(),
            default=df.columns.tolist(),
            help="Select and arrange columns in the desired order"
        )
        
        # Summary statistics
        st.write("Include Summary Statistics:")
        include_row_count = st.checkbox("Row Count", value=True)
        include_totals = st.checkbox("Column Totals", value=True)
        include_averages = st.checkbox("Column Averages", value=True)
        
        # Store selections in session state
        if 'report_content' not in st.session_state:
            st.session_state.report_content = {}
        
        st.session_state.report_content.update({
            'report_title': report_title,
            'selected_columns': selected_columns,
            'include_row_count': include_row_count,
            'include_totals': include_totals,
            'include_averages': include_averages
        })
    
    def _show_preview(self, df):
        """Show report preview"""
        st.subheader("👀 Report Preview")
        
        if 'report_content' not in st.session_state:
            st.warning("Please configure content options first")
            return
        
        # Generate preview with user's settings
        preview_buffer = self.generate_report(
            df,
            include_row_count=st.session_state.report_content.get('include_row_count', False),
            include_totals=st.session_state.report_content.get('include_totals', False),
            include_averages=st.session_state.report_content.get('include_averages', False),
            report_title=st.session_state.report_content.get('report_title', "Data Report")
        )
        
        st.session_state.preview_buffer = preview_buffer
        
        # Show download button for the preview
        st.download_button(
            label="⬇️ Download Preview",
            data=preview_buffer.getvalue(),
            file_name=f"report_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf"
        )
        
        # Display PDF using Streamlit's native PDF display
        try:
            # Create two columns for better layout
            col1, col2 = st.columns([1, 4])
            
            with col1:
                st.write("Preview Options:")
                zoom_level = st.slider("Zoom %", min_value=50, max_value=200, value=100, step=10)
            
            with col2:
                # Display PDF with custom width based on zoom level
                width = int(700 * (zoom_level/100))
                st.write("PDF Preview:")
                st.write(f'<iframe src="data:application/pdf;base64,{base64.b64encode(preview_buffer.getvalue()).decode()}" width="{width}" height="800"></iframe>', unsafe_allow_html=True)
                
                # Add a note about download option
                st.info("💡 If the preview is not visible, please use the download button above to view the PDF.")
        except Exception as e:
            st.error(f"Error displaying preview: {str(e)}")
            st.info("Please use the download button above to view the PDF.")
    
    def generate_report(self, df, include_row_count=True, include_totals=True, include_averages=True, report_title="Data Report"):
        """Generate the formatted report"""
        buffer = io.BytesIO()
        
        # Create the PDF document with current settings
        page_size = self.page_size
        if self.orientation == 'landscape':
            page_size = landscape(page_size)
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=page_size,
            leftMargin=self.margins[0],
            rightMargin=self.margins[1],
            topMargin=self.margins[2],
            bottomMargin=self.margins[3]
        )
        
        # Start building content
        elements = []
        
        # Add header image if present
        if self.header_image:
            elements.append(self.header_image)
            elements.append(Spacer(1, 20))
        
        # Create default title style if none exists
        if not self.title_style:
            self.title_style = ParagraphStyle(
                'CustomTitle',
                parent=self.styles['Title'],
                fontSize=24,
                spaceAfter=30,
                alignment=TA_CENTER
            )
        
        # Add title using the provided report_title
        title = Paragraph(report_title, self.title_style)
        elements.append(title)
        
        # Add timestamp
        timestamp_style = self.styles['Normal']
        timestamp_style.fontSize = 10
        timestamp_style.textColor = colors.gray
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elements.append(Paragraph(f"Generated on: {timestamp}", timestamp_style))
        elements.append(Spacer(1, 20))
        
        # Define default table style
        default_table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d5d7b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#808080')),
            ('ROWHEIGHT', (0, 0), (-1, -1), 20),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])
        
        # Add summary statistics only if requested
        if any([include_row_count, include_totals, include_averages]):
            summary_data = [["Metric", "Value"]]  # Header row
            
            if include_row_count:
                summary_data.append(["Total Rows", f"{len(df):,}"])
            
            numeric_cols = df.select_dtypes(include=['number']).columns
            if include_totals:
                for col in numeric_cols:
                    total = df[col].sum()
                    summary_data.append([f"Total {col}", f"{total:,.2f}"])
            
            if include_averages:
                for col in numeric_cols:
                    avg = df[col].mean()
                    summary_data.append([f"Average {col}", f"{avg:,.2f}"])
            
            if len(summary_data) > 1:  # Only add if we have data beyond the header
                summary_table = Table(summary_data)
                summary_table.setStyle(self.table_style or default_table_style)
                elements.append(summary_table)
                elements.append(Spacer(1, 20))
        
        # Add main data table
        data = [df.columns.tolist()]  # Header row
        data.extend(df.values.tolist())
        
        main_table = Table(data)
        main_table.setStyle(self.table_style or default_table_style)
        elements.append(main_table)
        
        # Add footer
        if self.footer_text:
            elements.append(Spacer(1, 20))
            footer_style = ParagraphStyle(
                'Footer',
                parent=self.styles['Normal'],
                fontSize=8,
                textColor=colors.gray,
                alignment=TA_CENTER
            )
            elements.append(Paragraph(self.footer_text, footer_style))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer

    def generate_email_content(self, report_title="Data Report", include_header=True):
        """Generate email content with proper formatting"""
        email_content = {
            'subject': f"Report: {report_title}",
            'body': f"""
Dear User,

Your report "{report_title}" has been generated and is attached to this email.

Report Details:
- Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Title: {report_title}

Please find the report attached to this email.

Best regards,
Tableau Data Reporter
            """.strip(),
            'include_header': include_header
        }
        return email_content 