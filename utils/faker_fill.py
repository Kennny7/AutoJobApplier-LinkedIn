"""
Generates plausible fake answers using the faker library.
Only used when user allows 'fill_random' for unknown questions.
"""

from faker import Faker
fake = Faker()

def generate_fake_answer(label: str) -> str:
    """Generate a fake answer based on label keywords."""
    label_lower = label.lower()
    if "name" in label_lower:
        return fake.name()
    if "email" in label_lower:
        return fake.email()
    if "phone" in label_lower or "mobile" in label_lower:
        return fake.phone_number()
    if "address" in label_lower or "street" in label_lower:
        return fake.street_address()
    if "city" in label_lower:
        return fake.city()
    if "state" in label_lower:
        return fake.state()
    if "zip" in label_lower:
        return fake.zipcode()
    if "country" in label_lower:
        return fake.country()
    if "url" in label_lower or "linkedin" in label_lower:
        return f"https://www.linkedin.com/in/{fake.user_name()}"
    if "salary" in label_lower or "ctc" in label_lower:
        return fake.random_int(min=50000, max=200000)
    if "years" in label_lower or "experience" in label_lower:
        return str(fake.random_int(min=1, max=15))
    if "notice" in label_lower:
        return str(fake.random_int(min=15, max=90))
    if "company" in label_lower or "employer" in label_lower:
        return fake.company()
    if "headline" in label_lower:
        return fake.job()
    if "summary" in label_lower or "cover" in label_lower:
        return fake.paragraph(nb_sentences=3)
    # Default vague answer
    return "I have relevant experience and skills."